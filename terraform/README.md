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

Switching `reduced` → `full` changes `frontend_url` and `api_url`, so `VITE_API_URL` on the `staging` GitHub Environment has to be re-copied from `frontend_api_base_url` afterwards. The access gate no longer changes it: the frontend calls the API host in every environment.

### Staging access gate

When WebbPulse-Platform sets `staging_access_gate = true` (and the profile is `full`), `staging_access_gate.tf` instantiates `app.terraform.io/WebbPulse/platform-modules/aws//modules/staging-access-gate` as `carmodpicker-staging` and the rest of the configuration wires it in, every edit gated on `local.staging_gate_enabled` so the production plan is a no-op:

- **CloudFront**: one extra origin (the gate's login Lambda function URL), `trusted_key_groups` on the default behavior, and ordered behaviors for `/_auth/*` (login origin) and `/index.html` (S3, no key group, so the 403/404 SPA fallback still works). Only the frontend goes through CloudFront; the API is not proxied. The viewer-request association switches from `frontend_uri_rewrite` to the gate's function, which runs the same `appHandler` from `cloudfront_functions/app_handler.js.tftpl` before its session check.
- **HTTP API**: `disable_execute_api_endpoint = true` and the `$default` route uses the module's REQUEST authorizer, which has no identity sources and a TTL of 0. It admits an `OPTIONS` preflight, a request carrying the `x-origin-verify` header, or a browser request carrying the gate's CloudFront signed cookies; everything else gets a 401.
- **Deploy role**: `ssm:GetParameter` on `/carmodpicker-staging/access-gate/origin-verify`, for any pipeline step that must call `api.staging.carmodpicker.com` directly (send the value as `x-origin-verify`; read it with `aws ssm get-parameter --with-decryption` and mask it).
- **Frontend**: API calls go to `https://api.staging.carmodpicker.com` exactly as production goes to `https://api.carmodpicker.com`. Set `VITE_API_URL` on the `staging` GitHub Environment to the `frontend_api_base_url` output (`https://api.staging.carmodpicker.com`; the frontend appends `/api`). The axios client sends `withCredentials: true`, and the cookies are set on `Domain=staging.carmodpicker.com` with `SameSite=Lax`, so a request from `www.staging` to `api.staging` is same-site and carries them. `/health` and `/ready` stay at the API root and are reached at `https://api.staging.carmodpicker.com/health` with the header.
- **Chrome extension**: the extension talks to `api.staging.carmodpicker.com/api` directly and cannot complete the hosted UI flow, so it does not work against a gated staging without the header.

Outputs: `staging_access_gate_hosted_ui`, `staging_access_gate_user_pool_id`, `frontend_api_base_url`.

### Production cutover (completed 2026-09-06)

Production ran App Runner + RDS PostgreSQL alongside Lambda + DynamoDB until the Lambda path was proven, then the legacy stack was destroyed. The data was copied with `backend/scripts/backfill_from_postgres.py`, `api.carmodpicker.com` was flipped to the HTTP API alias, and the VPC, RDS, ECR and App Runner resources were removed. The last RDS snapshot is `carmodpicker-production-final-snapshot` in the production account; delete it once nothing needs the old data.

## Shared platform modules

Most of this stack is now assembled from `app.terraform.io/WebbPulse/platform-modules/aws`, pinned at `~> 1.1` or later:

| Module | Instantiated in | What it owns |
| --- | --- | --- |
| `staging-dns` | `route53.tf` | The hosted zone for the served domain and, in staging only, the NS delegation written into the parent zone through `aws.parent_dns`. |
| `http-api` | `apigateway.tf` | The HTTP API, its `$default` stage, integration, route, invoke permission, custom domain, mapping and alias record. |
| `staging-access-gate` | `staging_access_gate.tf` | Cognito sign-in and CloudFront signed cookies in front of staging. See below. |
| `spa-frontend` | `cloudfront.tf` | The frontend bucket, its public access block, the origin access control and bucket policy, the CloudFront distribution with the access-gate origins and behaviors, and the apex and `www` alias records. |
| `ecr-repository` | `ecr.tf` | One ECR repository and lifecycle policy per per-domain Lambda, `carmodpicker-<env>/<domain>`. |
| `github-actions-role` | `iam_github_actions.tf` | The GitHub Actions OIDC provider, the `github-actions-deploy` role and its inline deploy policy. |

The adoption was a pure state move: the speculative plans on both workspaces read `0 to add, 0 to change, 0 to destroy`. The `moved` blocks that carried the state across have been applied in both workspaces and are no longer in the configuration.

What stays hand-written is what a single-provider module cannot own: the ACM certificates (`acm.tf`, one in `aws.us_east_1` for CloudFront and one regional for the API) with their DNS validation records, the CloudFront Function in `cloudfront_function.tf`, and the SES and verification records in `route53.tf`.

## File map

| File | What it manages |
| --- | --- |
| `versions.tf` | Terraform version pin, AWS + archive provider versions, HCP Terraform cloud block (production workspace; the staging workspace overrides it). |
| `providers.tf` | Default `aws` provider, `aws.us_east_1` alias (CloudFront certs), `aws.parent_dns` alias that assumes `route53_write_role_arn` when set (staging NS delegation). |
| `variables.tf` | Input variables: region, environment, shaping toggles above, throttling, secrets. |
| `locals.tf` | `project`, `prefix` (`carmodpicker-<env>`), `custom_domain`, `domain_name` (served domain), `active_domain` (served domain, or the apex when no custom domain is bound), `parent_delegation`, `email_from`, `frontend_url`, `api_url`, `allowed_origins`. |
| `data.tf` | `aws_caller_identity`, `aws_region` lookups for ARN construction. |
| `outputs.tf` | API/Lambda/DynamoDB/CloudFront identifiers plus everything the deploy workflows need, including `domain_lambda_function_names`, `domain_lambda_function_arns` and `domain_lambda_log_group_names`, which carry only the per-domain functions that exist. |
| `dynamodb.tf` | One `aws_dynamodb_table` per entry in `dynamodb_tables.json`, on-demand billing, PITR + deletion protection in production. |
| `dynamodb_tables.json` | Generated from `backend/app/db/dynamo/tables.py` by `backend/scripts/export_dynamo_tables.py`; a backend test fails when it is stale. |
| `lambda.tf` | Execution role (DynamoDB on `<prefix>-*`, SES, user-images S3, app secret, logs, X-Ray), log group, placeholder zip, the `<prefix>-api` function. |
| `lambda_placeholder/` | Source of the placeholder zip Terraform uploads on first create; code changes are ignored afterwards so the deploy workflow owns them. |
| `lambda_domains.tf` | `local.lambda_domains` (per-domain memory, write tables, read tables, whether it reads the app secret and the user images bucket), `var.bootstrap_image_tag`, `module "lambda_domain"` (`platform-modules/aws//modules/lambda-function`, `package_type = "Image"`, `arm64`, 29 s, 7-day logs, Active tracing) and one `aws_iam_role_policy` per domain. One entry today, `media`; rows 18 through 31 of the split plan add the other eight. Nothing routes to these functions until row 14. |
| `apigateway.tf` | `module "api"` (`platform-modules/aws//modules/http-api`): HTTP API with a `$default` Lambda proxy route, `$default` stage with throttling + JSON access logs, invoke permission, and the custom domain, mapping and alias record when `local.custom_domain`. |
| `s3.tf` | `user-images` (private), `crawl-data` (private), `lambda-artifacts` (versioned, 30-day noncurrent expiry). The frontend bucket moved into `module "frontend"`. |
| `cloudfront.tf` | `module "frontend"` (`platform-modules/aws//modules/spa-frontend`): the frontend bucket and its OAC and policy, the distribution with managed cache/origin/headers policies, the SPA 403/404 fallback, the access-gate origins and behaviors, and the apex and `www` alias records. Aliases and the ACM cert apply only with a custom domain. |
| `cloudfront_function.tf` | Viewer-request function `frontend_uri_rewrite`: `cloudfront_functions/app_handler.js.tftpl` (apex → www 301 and `/foo` → `/foo/index.html` rewrite for prerendered routes, as `appHandler`) wrapped by `uri_rewrite.js.tftpl` as `handler`. Unused on staging while the access gate is on. |
| `staging_access_gate.tf` | `module "staging_access_gate"` (count 0 or 1): Cognito user pool, login Lambda, CloudFront key group and function, HTTP API authorizer, SSM secrets. See "Staging access gate". |
| `acm.tf` | Wildcard cert for the served domain in `us-east-1` (CloudFront) and a regional cert for `api.<domain>` (HTTP API), both DNS-validated; validation waits on the staging delegation record. |
| `route53.tf` | `module "staging_dns"` (`platform-modules/aws//modules/staging-dns`): the hosted zone for the served domain plus, in staging, the NS delegation into the parent zone through `aws.parent_dns`. Then the SES DKIM/MAIL-FROM/DMARC and verification records. The apex and `www` alias records live in `module "frontend"`, the `api` alias record in `module "api"`. |
| `ses.tf` | SESv2 configuration set, domain identity (custom domain) or mailbox identity (`email_from`), custom MAIL FROM, SNS topic + subscription for bounces/complaints, account-level VDM. |
| `secretsmanager.tf` | `<prefix>/app`, the one JSON secret per environment (`SECRET_KEY`, `SENTRY_DSN`, `EXTENSION_API_KEY`), resolved by the Lambda on the first read of a secret through `APP_SECRETS_ARN`, not at import. `EXTENSION_API_KEY` comes from `var.extension_api_key` and is the shared secret `POST /api/parts/price-history` accepts in the `X-API-Key` header; it is **not set on any workspace yet**, and until an operator adds it as a sensitive variable on `CarModPicker` and `CarModPicker-staging` the key stays empty and that route accepts admin bearer tokens only. |
| `ecr.tf` | `module "registry"` (`platform-modules/aws//modules/ecr-repository`): one ECR repository plus lifecycle policy per entry in `local.lambda_domain_names`, named `carmodpicker-<env>/<domain>`, IMMUTABLE tags, scan on push, keep the last 10 `sha-` tagged images, untagged expired after a day. `backend/Dockerfile` builds what they hold: one image per domain from a shared base image in the Artifacts account, `arm64`, selected by `ARG DOMAIN`, tagged `sha-<commit>`. Nothing deploys from them yet; the workflow that pushes and deploys is the split plan's row 12. |
| `iam_github_actions.tf` | `module "github_actions_role"` (`platform-modules/aws//modules/github-actions-role`): GitHub OIDC provider + `github-actions-deploy` role: Lambda code updates, artifacts upload, frontend sync, invalidation, and (gate on) reading the origin-verify SSM parameter. |
| `monitoring.tf` | Alarms SNS topic; Lambda errors/throttles, HTTP API 5xx and p99 integration latency, one aggregate DynamoDB throttle alarm across every table. |
| `management.tf` | Tag-based Resource Group, Cost Explorer anomaly monitor + daily email subscription, monthly cost budgets. |

## Conventions

- **Naming**: every resource name starts with `local.prefix` = `carmodpicker-<environment>`.
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform` applied globally via provider `default_tags`.
- **Secrets**: values flow HCP workspace variable → `var.*` → Secrets Manager. The Lambda resolves `<prefix>/app` through `APP_SECRETS_ARN` on the first read of a secret field, not at import (`backend/app/core/config.py`, `backend/app/core/secrets.py`). A function that reads no secret makes no call and needs no `secretsmanager:GetSecretValue` grant. No secret values live in Terraform state outputs or version control.
- **Lambda code is not Terraform's**: the function is created with a placeholder and `ignore_changes` on the package attributes. `backend-deploy.yml` uploads the real zip to `<prefix>-lambda-artifacts` and calls `update-function-code`. The same division holds for the per-domain image functions once they exist: `deploy-backend.yml` builds the nine images into the `ecr.tf` repositories and calls `update-function-code` with a digest-pinned image URI, and `image_uri` goes on the module's `ignore_changes` list so the next apply does not revert a deploy back to the bootstrap tag. Nothing in this root reads an image tag except that one bootstrap variable.
- **The nine ECR repositories are IMMUTABLE**, which is a constraint on CI rather than on Terraform: a rerun of a workflow for the same commit would push a `sha-<40 hex>` tag that already exists and fail. The build job's `skip-if-tag-exists` guard resolves the tag with `aws ecr batch-get-image` and skips the build when it already resolves. `describe-images` is the wrong call for the guard and is deliberately not used: it can return metadata for a tag that has no manifest, and the deploy role holds `ecr:DescribeImages` on the shared base image repository but not on the nine.
- **No VPC**: the Lambda is not in a VPC and there is no NAT Gateway; every dependency is reached over public AWS endpoints.

## HCP workspace variables

Set per workspace, not in `.tfvars`:

- `environment` and `staging_profile` — pushed from the WebbPulse-Platform repo.
- `parent_route53_zone_id` and `route53_write_role_arn` — staging only, pushed from the WebbPulse-Platform repo; required once the profile is `full`.
- `staging_access_gate` and `staging_access_users` — staging only, pushed from the WebbPulse-Platform repo; turn on the staging access gate.
- `secret_key`, `sentry_dsn` — sensitive, set by hand.
- `extension_api_key` — sensitive, set by hand, **not yet set on either workspace**. The shared secret `POST /api/parts/price-history` accepts in the `X-API-Key` header, for the Chrome extension and ingestion jobs. It lands in the `<prefix>/app` JSON as `EXTENSION_API_KEY`. Leaving it unset is a supported state and not a startup failure: the API-key path is simply closed and the route accepts admin bearer tokens only. To turn the key path on, set it on `CarModPicker` and `CarModPicker-staging` (distinct values per environment), apply, then put the same value in the Chrome extension's options page.
- `bootstrap_image_tag`: the `sha-<40 hex>` image tag every function in `local.lambda_domains` is created from, set by hand once per workspace. It must already exist in each of those domains' ECR repositories before the apply, because Lambda pulls and optimises the image at `CreateFunction` and a tag that does not resolve fails the create. It is a seed and nothing more: `image_uri` is on the module's `ignore_changes` list, so `deploy-backend.yml` owns the image afterwards and this value never needs changing. Staging holds `sha-ef2e455df9e14ac7251ee1b13331603ff7a90234`; production needs its own, pointing at a tag pushed into the production account's repositories, before the first per-domain function is planned there.
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
| `VITE_API_URL` | `frontend_api_base_url` (`https://api.carmodpicker.com` in production, `https://api.staging.carmodpicker.com` on staging) |
| `CWS_EXTENSION_ID` | Chrome Web Store extension id |

Secret: `TFC_API_TOKEN`.

### Repository variables

One deploy-adjacent variable is repository-scoped rather than environment-scoped, because a `pull_request` job cannot read an Environment whose deployment branch policy admits only `main` and `staging`:

| Variable | Output | Notes |
| --- | --- | --- |
| `CI_AWS_ROLE_ARN` | `github_actions_ci_role_arn` | Take the **staging** workspace's value. The three CI workflows assume it through OIDC purely to mint a read-only CodeArtifact token so `pip install` can resolve `webbpulse`. The role holds the CodeArtifact reads and nothing else, and its trust names `pull_request` plus the `staging` and `main` branch refs rather than a wildcard, so a pull request cannot reach the deploy role. |

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
2. Set `sentry_dsn` on the HCP workspace; the next apply writes it into `<prefix>/app`.
3. Add frontend Sentry secrets to GitHub Actions: `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
4. Redeploy so the new value is picked up.

Until step 2 completes, the Sentry SDK `init_sentry()` helper no-ops gracefully (env-gate handles empty DSN).
