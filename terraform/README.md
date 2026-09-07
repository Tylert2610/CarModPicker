# Terraform — CarModPicker AWS Infrastructure

Terraform configuration for the CarModPicker AWS stack. One root module, two HCP Terraform workspaces:

| Workspace | AWS account | VCS branch | `environment` | `staging_profile` |
| --- | --- | --- | --- | --- |
| `CarModPicker` | 734702670403 | `main` | `production` | — |
| `CarModPicker-staging` | 748861776298 | `staging` | `staging` | `full` (intended), `reduced` (fallback) |

State lives in HCP Terraform; applies are triggered by pushing to the bound branch. Production is manual-apply.

## Architecture at a glance

```
                  ┌────────────────────────────────────────┐
Route53 ──┐       │              CloudFront                │
          ├──── www.carmodpicker.com ──▶  S3 (frontend)    │
          │       │  + uri_rewrite CloudFront Function     │
          │       └────────────────────────────────────────┘
          │
          ├──── carmodpicker.com ──▶ S3 website redirect ──▶ www
          │
          └──── api.carmodpicker.com ──▶ HTTP API ──▶ Lambda (app.lambda_handler) ──▶ DynamoDB
                                                          ├──▶ Secrets Manager (<prefix>/app)
                                                          ├──▶ S3 (user images)
                                                          └──▶ SES
```

Single-region deployment in `us-west-2`. The CloudFront cert lives in `us-east-1` via the `aws.us_east_1` provider alias; the HTTP API cert is regional. Staging serves the same shape one label down: `staging.carmodpicker.com`, `www.staging.carmodpicker.com`, `api.staging.carmodpicker.com`, from a child zone it owns and that the parent zone delegates to (see "Staging profiles").

## Environment shaping

These inputs decide what a workspace builds. Every other resource is unconditional.

| Variable | Default | Effect |
| --- | --- | --- |
| `custom_domain_enabled` | `null` → `true` in production or when `staging_profile = full` | Hosted zone, ACM certs, custom-domain records, SES domain identity, CloudFront aliases, HTTP API domain name. |
| `domain_name` | `carmodpicker.com` | Registered apex. `local.domain_name` is the domain actually served: `domain_name` in production, `staging.<domain_name>` in staging. Every hostname, the hosted zone, the ACM certs, the SES identity and the CloudFront apex→www redirect derive from it. |
| `parent_route53_zone_id` | `null` | Staging only: hosted zone id of `domain_name` in the production account, where the NS delegation for `staging.<domain_name>` is written. Required when staging has a custom domain. |
| `route53_write_role_arn` | `null` | Staging only: role in the production account, scoped to that one NS record, assumed by the `aws.parent_dns` provider alias. Required when staging has a custom domain. |
| `email_from` | `null` → `no-reply@<served domain>` with a custom domain, `no-reply@<domain_name>` without | Sender address for transactional mail; must belong to the SES identity the environment verifies. |
| `staging_access_gate` | `false` | Staging only, pushed by WebbPulse-Platform. With `staging_profile = full`, puts the site and API behind the shared staging access gate (see below). Production never receives it. |
| `staging_access_users` | `[]` | Staging only, pushed by WebbPulse-Platform. Email addresses allowed through the gate; each becomes an invited Cognito user. |

### Staging profiles

`staging_profile` is `reduced` or `full` (`none` is rejected — a staging workspace with nothing in it should not exist).

- **`full`** (intended): everything `reduced` builds plus real DNS. The staging account owns a hosted zone for `staging.carmodpicker.com`; in the same apply the `aws.parent_dns` provider assumes `route53_write_role_arn` in the production account and writes the `NS` delegation for `staging.carmodpicker.com` into `parent_route53_zone_id` (the `carmodpicker.com` zone owned by the production workspace). Both ACM validations `depends_on` that record so validation does not start before the child zone is reachable. Hostnames: `staging.carmodpicker.com` (CloudFront alias, 301 → www), `www.staging.carmodpicker.com` (SPA), `api.staging.carmodpicker.com` (HTTP API custom domain), `bounce.staging.carmodpicker.com` (SES MAIL FROM). SES uses the domain identity exactly as production does; `email_from` defaults to `no-reply@staging.carmodpicker.com`. Both variables are pushed to the workspace by WebbPulse-Platform; until they are, the profile must stay `reduced`.
- **`reduced`** (fallback): DynamoDB + Lambda + HTTP API + CloudFront + S3 + SES, no custom domain. The frontend is served from the CloudFront hostname, the API from the `execute-api` endpoint, and SES sends from a mailbox identity (`email_from`, defaulting to `no-reply@carmodpicker.com`) instead of a domain identity. Outputs `frontend_url` and `api_url` carry the generated hostnames.

Switching `reduced` → `full` changes `frontend_url` and `api_url`, and turning the access gate on changes `frontend_api_base_url`, so `VITE_API_URL` on the `staging` GitHub Environment has to be re-copied from `frontend_api_base_url` afterwards.

### Staging access gate

When WebbPulse-Platform sets `staging_access_gate = true` (and the profile is `full`), `staging_access_gate.tf` instantiates `app.terraform.io/WebbPulse/platform-modules/aws//modules/staging-access-gate` as `carmodpicker-staging` and the rest of the configuration wires it in, every edit gated on `local.staging_gate_enabled` so the production plan is a no-op:

- **CloudFront**: two extra origins (the gate's login Lambda function URL, and `api.staging.carmodpicker.com` with the `x-origin-verify` header), `trusted_key_groups` on the default behavior, and ordered behaviors for `/_auth/*` (login origin), `/api/*` (API origin, signed cookies required) and `/index.html` (S3, no key group, so the 403/404 SPA fallback still works). The viewer-request association switches from `frontend_uri_rewrite` to the gate's function, which runs the same `appHandler` from `cloudfront_functions/app_handler.js.tftpl` before its session check.
- **HTTP API**: `disable_execute_api_endpoint = true` and the `$default` route uses the module's REQUEST authorizer, so the API host only answers requests carrying the header CloudFront adds.
- **Deploy role**: `ssm:GetParameter` on `/carmodpicker-staging/access-gate/origin-verify`, for any pipeline step that must call `api.staging.carmodpicker.com` directly (send the value as `x-origin-verify`; read it with `aws ssm get-parameter --with-decryption` and mask it).
- **Frontend**: API calls must go through the site origin so the cookies travel with them. Set `VITE_API_URL` on the `staging` GitHub Environment to the `frontend_api_base_url` output (`https://www.staging.carmodpicker.com`; the frontend appends `/api`). `/health` and `/ready` stay at the API root and are reached at `https://api.staging.carmodpicker.com/health` with the header.
- **Chrome extension**: the extension talks to `api.staging.carmodpicker.com/api` directly and cannot complete the hosted UI flow, so it does not work against a gated staging without the header.

Outputs: `staging_access_gate_hosted_ui`, `staging_access_gate_user_pool_id`, `frontend_api_base_url`.

### Production cutover (completed 2026-09-06)

Production ran App Runner + RDS PostgreSQL alongside Lambda + DynamoDB until the Lambda path was proven, then the legacy stack was destroyed. The data was copied with `backend/scripts/backfill_from_postgres.py`, `api.carmodpicker.com` was flipped to the HTTP API alias, and the VPC, RDS, ECR and App Runner resources were removed. The last RDS snapshot is `carmodpicker-production-final-snapshot` in the production account; delete it once nothing needs the old data.

## Shared platform modules

Most of this stack is now assembled from `app.terraform.io/WebbPulse/platform-modules/aws`, pinned at `~> 1.3`:

| Module | Instantiated in | What it owns |
| --- | --- | --- |
| `staging-dns` | `route53.tf` | The hosted zone for the served domain and, in staging only, the NS delegation written into the parent zone through `aws.parent_dns`. |
| `http-api` | `apigateway.tf` | The HTTP API, its `$default` stage, integration, route, invoke permission, custom domain, mapping and alias record. |
| `spa-frontend` | `cloudfront.tf` | The frontend bucket with its OAC and policy, the CloudFront distribution, the apex and `www` alias records, and the access-gate wiring. |
| `staging-access-gate` | `staging_access_gate.tf` | Cognito sign-in and CloudFront signed cookies in front of staging. See below. |

The adoption was a pure state move: every `moved` block lives in `moved.tf` and the speculative plans on both workspaces read `0 to add, 0 to change, 0 to destroy`. What stays hand-written here is what a single-provider module cannot own: the ACM certificates (`acm.tf`, one in `aws.us_east_1` for CloudFront and one regional for the API) with their DNS validation records, the CloudFront Function in `cloudfront_function.tf`, and the SES and verification records in `route53.tf`. The GitHub Actions role in `iam_github_actions.tf` is also still hand-written, for the reason given at the top of that file.

## File map

| File | What it manages |
| --- | --- |
| `versions.tf` | Terraform version pin, AWS + archive provider versions, HCP Terraform cloud block (production workspace; the staging workspace overrides it). |
| `providers.tf` | Default `aws` provider, `aws.us_east_1` alias (CloudFront certs), `aws.parent_dns` alias that assumes `route53_write_role_arn` when set (staging NS delegation). |
| `variables.tf` | Input variables: region, environment, shaping toggles above, throttling, secrets. |
| `locals.tf` | `project`, `prefix` (`carmodpicker-<env>`), `custom_domain`, `domain_name` (served domain), `active_domain` (served domain, or the apex when no custom domain is bound), `parent_delegation`, `email_from`, `frontend_url`, `api_url`, `allowed_origins`. |
| `data.tf` | `aws_caller_identity`, `aws_region` lookups for ARN construction. |
| `moved.tf` | Every `moved` block in one place: the older count-conversion renames, and the moves that took the hand-written resources into the four shared platform modules. |
| `outputs.tf` | API/Lambda/DynamoDB/CloudFront identifiers plus everything the deploy workflows need. |
| `dynamodb.tf` | One `aws_dynamodb_table` per entry in `dynamodb_tables.json`, on-demand billing, PITR + deletion protection in production. |
| `dynamodb_tables.json` | Generated from `backend/app/db/dynamo/tables.py` by `backend/scripts/export_dynamo_tables.py`; a backend test fails when it is stale. |
| `lambda.tf` | Execution role (DynamoDB on `<prefix>-*`, SES, user-images S3, app secret, logs, X-Ray), log group, placeholder zip, the `<prefix>-api` function. |
| `lambda_placeholder/` | Source of the placeholder zip Terraform uploads on first create; code changes are ignored afterwards so the deploy workflow owns them. |
| `apigateway.tf` | `module "api"` (`platform-modules/aws//modules/http-api`): HTTP API with a `$default` Lambda proxy route, `$default` stage with throttling + JSON access logs, invoke permission, and the custom domain, mapping and alias record when `local.custom_domain`. |
| `s3.tf` | `user-images` (private), `crawl-data` (private), `lambda-artifacts` (versioned, 30-day noncurrent expiry). The frontend bucket belongs to `module "frontend"`. |
| `cloudfront.tf` | `module "frontend"` (`platform-modules/aws//modules/spa-frontend`): the private frontend bucket and its OAC and policy, the distribution with the managed cache/origin/headers policies and the SPA 403/404 fallback, the apex and `www` alias records, and the whole access-gate wiring through its `access_gate` argument. Aliases and the ACM cert apply only with a custom domain. |
| `cloudfront_function.tf` | Viewer-request function `frontend_uri_rewrite`: `cloudfront_functions/app_handler.js.tftpl` (apex → www 301 and `/foo` → `/foo/index.html` rewrite for prerendered routes, as `appHandler`) wrapped by `uri_rewrite.js.tftpl` as `handler`. Unused on staging while the access gate is on. |
| `staging_access_gate.tf` | `module "staging_access_gate"` (count 0 or 1): Cognito user pool, login Lambda, CloudFront key group and function, HTTP API authorizer, SSM secrets. See "Staging access gate". |
| `acm.tf` | Wildcard cert for the served domain in `us-east-1` (CloudFront) and a regional cert for `api.<domain>` (HTTP API), both DNS-validated; validation waits on the staging delegation record. |
| `route53.tf` | `module "staging_dns"` (`platform-modules/aws//modules/staging-dns`): the hosted zone for the served domain plus, in staging, the NS delegation into the parent zone through `aws.parent_dns`. Then the SES DKIM/MAIL-FROM/DMARC and verification records. The apex, `www` and `api` alias records live in `module "frontend"` and `module "api"`. |
| `ses.tf` | SESv2 configuration set, domain identity (custom domain) or mailbox identity (`email_from`), custom MAIL FROM, SNS topic + subscription for bounces/complaints, account-level VDM. |
| `secretsmanager.tf` | `<prefix>/app` JSON secret (`SECRET_KEY`, `SENTRY_DSN`) read by the Lambda at import, plus the standalone `secret-key` / `sentry-dsn` secrets. |
| `iam_github_actions.tf` | GitHub OIDC provider + `github-actions-deploy` role: Lambda code updates, artifacts upload, frontend sync, invalidation, and (gate on) reading the origin-verify SSM parameter. Still hand-written, see the note at the top of the file. |
| `monitoring.tf` | Alarms SNS topic; Lambda errors/throttles, HTTP API 5xx and p99 integration latency, per-table DynamoDB throttle events. |
| `management.tf` | Tag-based Resource Group, Cost Explorer anomaly monitor + daily email subscription, monthly cost budgets. |

## Conventions

- **Naming**: every resource name starts with `local.prefix` = `carmodpicker-<environment>`.
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform` applied globally via provider `default_tags`.
- **Secrets**: values flow HCP workspace variable → `var.*` → Secrets Manager. The Lambda reads `<prefix>/app` at import time through `APP_SECRETS_ARN` (`backend/app/core/secrets.py`). No secret values live in Terraform state outputs or version control.
- **Lambda code is not Terraform's**: the function is created with a placeholder and `ignore_changes` on the package attributes. `backend-deploy.yml` uploads the real zip to `<prefix>-lambda-artifacts` and calls `update-function-code`.
- **No VPC**: the Lambda is not in a VPC and there is no NAT Gateway; every dependency is reached over public AWS endpoints.

## HCP workspace variables

Set per workspace, not in `.tfvars`:

- `environment` and `staging_profile` — pushed from the WebbPulse-Platform repo.
- `parent_route53_zone_id` and `route53_write_role_arn` — staging only, pushed from the WebbPulse-Platform repo; required once the profile is `full`.
- `staging_access_gate` and `staging_access_users` — staging only, pushed from the WebbPulse-Platform repo; turn on the staging access gate.
- `secret_key`, `sentry_dsn` — sensitive, set by hand.
- `custom_domain_enabled`, `domain_name`, `email_from` — optional, see above.

AWS credentials are injected automatically via HCP Terraform dynamic provider credentials (no static keys).

## GitHub Environments

The deploy workflows select the `production` or `staging` GitHub Environment from the branch and read every value from it. Populate each from this workspace's outputs:

| Variable | Output |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `github_actions_role_arn` |
| `TFC_WORKSPACE_ID` | HCP workspace id (`ws-…`) |
| `LAMBDA_FUNCTION_NAME` | `lambda_function_name` |
| `LAMBDA_ARTIFACTS_BUCKET` | `lambda_artifacts_bucket` |
| `FRONTEND_S3_BUCKET` | `frontend_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` |
| `VITE_API_URL` | `frontend_api_base_url` (`https://api.carmodpicker.com` in production; `https://www.staging.carmodpicker.com` on staging while the access gate is on, otherwise `api_url`) |
| `CWS_EXTENSION_ID` | Chrome Web Store extension id |

Secret: `TFC_API_TOKEN`.

## Local validation

```bash
terraform fmt -check -recursive terraform/
cd terraform && terraform init -backend=false && terraform validate
```

`terraform plan` runs in HCP on push; the local checkout has no credentials and should not need any.

## Destroy / teardown notes

- DynamoDB tables have `deletion_protection_enabled = true` in production.
- Secrets use `recovery_window_in_days = 0` for immediate deletion.

## Bootstrap: Sentry

Sentry DSN provisioning is out-of-band (Terraform cannot create Sentry projects):

1. Create the Sentry project in the Sentry dashboard.
2. Set `sentry_dsn` on the HCP workspace; the next apply writes it into `<prefix>/app` and `<prefix>/sentry-dsn`.
3. Add frontend Sentry secrets to GitHub Actions: `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
4. Redeploy so the new value is picked up.

Until step 2 completes, the Sentry SDK `init_sentry()` helper no-ops gracefully (env-gate handles empty DSN).
