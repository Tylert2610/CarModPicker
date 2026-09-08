# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CarModPicker is a full-stack web application for managing car modifications. Users can track their cars, create build lists with parts, browse a global parts catalog, and log their builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend + React 19 (TypeScript) frontend, deployed on AWS as Lambda + HTTP API + DynamoDB. Infrastructure managed with Terraform (`terraform/`).

---

## Commands

### Backend (`backend/`)

```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Local services (requires Docker): DynamoDB Local on :8001, MinIO on :9000
docker-compose up -d
docker-compose down
python scripts/create_dynamo_tables.py   # create the app's tables in DynamoDB Local (idempotent)
python scripts/backfill_from_postgres.py --dry-run   # one-off Postgres -> DynamoDB copy (needs psycopg2-binary + DATABASE_URL)

# Table definitions live in app/db/dynamo/tables.py; regenerate the Terraform copy after editing
python scripts/export_dynamo_tables.py

# Per-domain container images. One Dockerfile, nine images, selected by DOMAIN.
# The dependency install resolves through CodeArtifact, so mint a token first.
export CODEARTIFACT_AUTH_TOKEN="$(aws codeartifact get-authorization-token \
  --domain webbpulse --domain-owner 432410731887 \
  --region us-west-2 --query authorizationToken --output text)"
# The base image lives in the Artifacts account, so pulling it needs that login.
aws ecr get-login-password --region us-west-2 \
  | docker login --username AWS --password-stdin \
    432410731887.dkr.ecr.us-west-2.amazonaws.com

scripts/build_image.sh media            # domains: identity, users, catalog,
                                        # vehicles, build-lists, build-logs,
                                        # moderation, media, ingestion
scripts/run_image.sh media              # serves on :8080 against DynamoDB Local
curl localhost:8080/health              # liveness, no I/O; what the adapter polls
curl localhost:8080/ready               # readiness, reads DynamoDB

# Tests — always run with -n auto for parallel execution
# Tests run against moto's in-memory DynamoDB — no services required
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto path/to/test_file.py       # single file
pytest -n auto -k "test_name"             # single test
# Rate limiting is disabled in tests by default; set ENABLE_RATE_LIMITING=true to test it

# Linting / formatting
black --config pyproject.toml .
isort .
pyright
bandit -r app
```

### Frontend (`frontend/`)

```bash
npm run dev           # dev server on port 4000 (proxies /api to backend)
npm run dev:staging   # use staging API
npm run dev:prod      # use production API
npm run build         # tsc -b && vite build
npm run lint          # eslint
npm run type-check    # tsc --noEmit
npm test              # vitest
npm run test:coverage
```

### Chrome Extension (`chrome-extension/`)

```bash
npm run build   # production build → dist/
npm run watch   # auto-rebuild on change (then reload in chrome://extensions/)
```

---

## Architecture

### Request flow

```
Browser / Chrome Extension
    → React frontend (port 4000, dev proxy /api → 8000)
    → FastAPI backend (port 8000, prefix /api; Lambda + HTTP API in AWS)
    → DynamoDB (DynamoDB Local in Docker locally, DynamoDB in AWS)
```

### Backend (`backend/app/`)

- **`main.py`** — The whole-surface application, kept as the import path everything already uses (`uvicorn app.main:app`, `lambda_handler.py`, the test suite). It is a thin wrapper over `app/composition/app.py` and holds no wiring of its own.
- **`composition/`** — Root A, every domain in one process. `wiring.py` holds the `Domain` descriptor and the shared app building (CORS, rate limiting, error handlers, the five root routes); `domains.py` names the nine domains and, for each, the routers it owns, its prefixes and tags, and whether it needs `SECRET_KEY`; `app.py` composes all nine and is what `main.py` serves.
- **`entrypoints/`** — Root B, one module per deployed function (`identity`, `users`, `catalog`, `vehicles`, `build_lists`, `build_logs`, `moderation`, `media`, `ingestion`). Each builds an application carrying one domain plus the five root routes. `domains.py` loads routers through a callable so importing a descriptor imports no endpoint module, which is what keeps a domain image to one domain; `backend/tests/entrypoints/` asserts it in a fresh interpreter with no AWS credentials.
- **`api/endpoints/`** — One file per domain (`auth`, `users`, `car_generations`, `parts`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_logs`, `votes`, `reports`, `images`, `search`, `admin`, `crawled_pages`, `part_manufacturers`, `categories`, `retailers`, `bug_reports`).
- **`db/dynamo/`** — DynamoDB layer: `tables.py` (every table and GSI, one `TableSpec` each), `repository.py` (generic `DynamoRepository[TModel]`), and one module per domain (`users`, `catalog`, `build_lists`, `build_logs`, `moderation`, ...) holding the Pydantic item models and their repositories. `registry.py` catalogues all twenty-five repositories as module, class and table names, and `api/dependencies/repositories.py` cuts per-domain `RepositoryBundle`s from it. A bundle carries only the repositories its domain declares in `app/composition/domains.py`, builds each one on first access, and raises `RepositoryNotInBundle` for anything outside the set, so a `media` process never constructs a `users` repository. `Repositories` is still the annotation every route uses; `bind_repositories` binds the right bundle per application.
- **`api/schemas/`** — Pydantic v2 request/response schemas.
- **`api/services/`** — Business logic layer called by endpoints.
- **`api/dependencies/auth.py`** — FastAPI `Depends()` helpers: `get_current_user`, `get_optional_current_user`, `get_current_admin_user`, `get_current_superuser`.
- **`api/middleware/`** — Rate limiting + content-length guard + error handlers.
- **`api/utils/`** — Shared patterns: `BaseDynamoEndpointRouter` (generic CRUD router over `BaseDynamoCRUDService`), `EndpointRegistry` (standardized router registration), pagination, authorization, subscription checks.
- **`core/`** — Config, logging, email templates (React Email HTML, sent via SES), car/category seed data.
- **`backend/app/core/sentry.py`** — Sentry SDK 2.x init helper. Env-gated (TESTING+APP_ENVIRONMENT+DSN). Scope processor reads request_id/user_id from log_context ContextVars.

**Auth:** JWT (HS256, configurable expiry 15 min–7 days per user preference) + bcrypt passwords + optional TOTP 2FA. Requires email verification before login is allowed. Email sent via AWS SES with IAM role auth.

**Images:** Uploaded to S3 (`carmodpicker-prod-user-images`, private) via boto3; presigned URLs used for serving. Pillow used for processing.

**Special endpoints:**
- `GET /health` — liveness check (always 200)
- `GET /ready` — readiness check (503 until DynamoDB answers a `DescribeTable` on the users table)

### Backend patterns

Endpoints read and write through repositories from `app/db/dynamo/`, injected via `get_repositories()`. Simple domains use `BaseDynamoEndpointRouter` (generic CRUD over `BaseDynamoCRUDService`) rather than hand-rolled route functions; when adding a new domain, add a `TableSpec`, an item model plus repository, and follow that pattern. Votes and reports are polymorphic over `entity_type` / `entity_id` and served by the unified `votes.py` / `reports.py` endpoints backed by `VoteService` / `ReportService` on DynamoDB.

### Frontend (`frontend/src/`)

- **`pages/`** — Route-level components (lazy-loaded).
- **`components/`** — Shared UI components.
- **`api/`** — Axios-based API client modules (one per backend domain).
- **`contexts/`** — React contexts (auth, user state).
- **`hooks/`** — Custom React hooks.
- React Router 7 for routing; Tailwind CSS 4 for styling.
- **Subscription tiers** gate features and ad display.

### Chrome Extension (`chrome-extension/src/`)

Content scripts scrape product data from retailer pages and POST to the backend API. Files that need an extension reload in `chrome://extensions/`: `manifest.json`, `background.ts`, `popup.html/css`. Content/popup/options scripts auto-update on next page load / popup reopen.

---

## Branching and deploys

```
feature/* ──PR──▶ staging ──PR──▶ main
                     │              │
                     ▼              ▼
           AWS 748861776298   AWS 734702670403
              (staging)          (production)
```

- Branch new work from `staging`, not `main`. PR into `staging`. Releasing is a PR from `staging` into `main` — that PR is the release boundary.
- Never commit directly to `main` or `staging`. Never force-push either. Stacked PRs bottom out on `staging`.
- Hotfixes branch from `main` and PR into `main`, then are immediately back-merged `main` → `staging`. Skipping the back-merge is how the branches silently diverge.
- Both accounts are `us-west-2`. Terraform Cloud org is `WebbPulse`.

**Protection is enforced by rulesets, with one bypass.** The WebbPulse org is on the GitHub Team plan, and repository rulesets cover both `main` and `staging`: pull request required, force-push and deletion blocked. The repository-admin role can bypass them, so the rulesets stop mistakes, not a determined admin. The real gate is Terraform Cloud manual apply on the production workspace: a merge cannot change AWS, only an apply can. CI runs on every PR but is not blocking — you have to read it.

### Workflows

Seven workflows in `.github/workflows/`, three CI and four deploy, each scoped by path.

| Workflow | Trigger | Paths |
|---|---|---|
| `backend-ci.yml` | `pull_request` → `main`, `staging` | `backend/**` |
| `frontend-ci.yml` | `pull_request` → `main`, `staging` | `frontend/**` |
| `chrome-extension-ci.yml` | `pull_request` → `main`, `staging` | `chrome-extension/**` |
| `backend-deploy.yml` | `push` → `main`, `staging` | `backend/**` |
| `deploy-backend.yml` | `push` → `main`, `staging`, plus `workflow_dispatch` | `backend/**` |
| `frontend-deploy.yml` | `push` → `main`, `staging` | `frontend/**` |
| `chrome-extension-deploy.yml` | `push` → `main` | `chrome-extension/**` |

The deploy workflows are fully independent. A backend merge never rebuilds the frontend.

`backend-deploy.yml` and `frontend-deploy.yml` pick their GitHub Environment from the branch (`main` → `production`, otherwise `staging`) and read every deploy-time value from that Environment. The backend deploy builds a Lambda zip (`requirements-lambda.txt` resolved for manylinux x86_64 / Python 3.13, plus `app/`), uploads it to the artifacts bucket keyed by commit SHA, waits for HCP Terraform to go idle, then runs `update-function-code` and `publish-version`.

**`backend-deploy.yml` and `deploy-backend.yml` are two workflows with confusingly similar names, and the distinction is which function they deploy.** `backend-deploy.yml` is the monolith's zip chain and deploys `carmodpicker-<env>-api`, which is still the only function any API Gateway route reaches. `deploy-backend.yml` is the per-domain container image chain from row 12 of `docs/migration/split-plan.md`: `resolve-env`, `build-images`, `image-map`, `existing-functions`, `deploy-images`, `smoke-domains`, building the nine domain images from the one `backend/Dockerfile` with `DOMAIN` selecting the entrypoint. They are separate files rather than one so that an image build cannot hold back or roll back the deploy that serves traffic. Section 6.5 of the split plan retires the monolith, and that is the PR that deletes `backend-deploy.yml` and leaves `deploy-backend.yml` as the only backend deploy.

Both halves of the image chain are gated by repository variables, and both are absent today, so `deploy-backend.yml` is inert until one is set. `BACKEND_IMAGE_BUILD_ENABLED` turns on the build, whose enabled run leaves nine images in ECR and changes no behaviour because nothing pulls them. `BACKEND_IMAGE_DEPLOY_ENABLED` turns on the deploy, which needs the domain functions to exist. `existing-functions` filters the image map down to the functions that actually exist before the deploy runs, so an estate part way through the cutover deploys what is there and skips what is not, rather than failing on `ResourceNotFoundException`.

**`chrome-extension-deploy.yml` stays `main`-only.** It publishes to the Chrome Web Store, not to AWS: patch-bump `manifest.json`, tag `chrome-extension-vX.Y.Z`, cut a GitHub Release, upload and publish the zip via the CWS API. A browser extension has no staging-account equivalent and there is no staging store listing, so a `staging` trigger would have nothing to deploy to. It is also the one sanctioned exception to "never commit directly to `main`" — it pushes its own version bump with `git push origin HEAD:main`.

### Environment-scoped variables

Deploy variables are **environment-scoped**: they live on the `production` and `staging` GitHub Environments, not the repository, so a `staging` push cannot silently pick up the production role. Nothing deploy-related is hardcoded in the workflows any more — the workspace id and the API URL are Environment variables too. Values come from the matching workspace's Terraform outputs (`terraform/README.md` maps each variable to its output). `VITE_API_URL` is `api_url`, which follows the served domain (`https://api.carmodpicker.com`, `https://api.staging.carmodpicker.com` once staging runs profile `full`), so it has to be re-copied when a profile flips; `frontend_url`, `domain_name`, `route53_zone_id` and `route53_zone_name_servers` are the other hostname-bearing outputs.

| Workflow | Variables | Secrets |
|---|---|---|
| `backend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `TFC_WORKSPACE_ID`, `LAMBDA_FUNCTION_NAME`, `LAMBDA_ARTIFACTS_BUCKET` | `TFC_API_TOKEN` |
| `deploy-backend.yml` | `AWS_DEPLOY_ROLE_ARN` (environment), `CODEARTIFACT_DOMAIN_OWNER`, `BACKEND_IMAGE_BUILD_ENABLED`, `BACKEND_IMAGE_DEPLOY_ENABLED` (all three repository-level) | none |
| `frontend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `TFC_WORKSPACE_ID`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `VITE_API_URL`, `CWS_EXTENSION_ID` | `TFC_API_TOKEN` |
| `chrome-extension-deploy.yml` | `CWS_CLIENT_ID`, `CWS_EXTENSION_ID` | `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN` |

`deploy-backend.yml` needs no `TFC_API_TOKEN`. Its Terraform wait is the reusable workflow's `aws lambda wait function-updated-v2` before and after each `update-function-code`, taken once for all functions rather than once per domain, which settles an in-flight apply without polling HCP at all. `AWS_DEPLOY_ROLE_ARN` is environment-scoped like every other deploy role, which is why the chain opens with a `resolve-env` job: a job that calls a reusable workflow with `uses:` may not carry an `environment:` key, so it cannot read an environment-scoped variable and `resolve-env` passes the ARN through a job output instead.

The backend and frontend deploys poll the HCP Terraform runs API with `TFC_API_TOKEN` and wait for the workspace named by `TFC_WORKSPACE_ID` to reach a terminal state before touching Lambda or S3 — that poll is what stops a code update racing an in-flight configuration change. Production polls `ws-oh1VvpTBPxmcrSYD`; staging polls `CarModPicker-staging`.

### A staging branch does not imply staging infrastructure

`terraform/` is one root module applied by two HCP workspaces: `CarModPicker` (production, bound to `main`, pinned in the `cloud` block in `versions.tf`) and `CarModPicker-staging` (bound to `staging`, `environment = staging`). `var.environment` feeds `local.prefix`, `local.domain_name` and every environment-dependent decision.

The intended staging profile is `full`: the same stack as production, served as `staging.carmodpicker.com` / `www.staging.carmodpicker.com` / `api.staging.carmodpicker.com`. The staging account owns the `staging.carmodpicker.com` hosted zone, and the same apply writes its `NS` delegation into the `carmodpicker.com` zone in the production account through the `aws.parent_dns` provider alias, which assumes `route53_write_role_arn` (scoped to that one record) and targets `parent_route53_zone_id`. WebbPulse-Platform pushes both variables to the workspace; SES uses the domain identity exactly as production does. `reduced` is the fallback while those variables are absent: no custom domain, frontend on the CloudFront hostname, API on the `execute-api` endpoint, SES on a mailbox identity. `none` is rejected. Staging is never auto-provisioned to mirror production.

### The Lambda migration stack

Production was cut over from App Runner + RDS PostgreSQL to Lambda + DynamoDB on 2026-09-06 and the legacy stack has been destroyed; `terraform/README.md` keeps a short record under "Production cutover". The only remaining Postgres artefact is `backend/scripts/backfill_from_postgres.py`, kept for reference.

The Lambda's code is not Terraform's: the function is created from a placeholder zip with `ignore_changes` on the package, and `backend-deploy.yml` owns every update after that. Its secrets come from the `<prefix>/app` JSON secret, resolved lazily on first read by `backend/app/core/config.py` when `APP_SECRETS_ARN` is set (an environment variable of the same name wins, so local dev and tests never call AWS). Importing the application performs no Secrets Manager call, which is what lets tooling import it without credentials; `Settings.require_secrets(...)` is the point-of-use check. DynamoDB tables are declared once, in `backend/app/db/dynamo/tables.py`; `backend/scripts/export_dynamo_tables.py` renders them to `terraform/dynamodb_tables.json` and `tests/db/test_dynamo_tables_json_up_to_date.py` fails when the two drift.

---

## Key Conventions

- **Tables:** Declare every table and index in `backend/app/db/dynamo/tables.py`, then run `python scripts/export_dynamo_tables.py` so `terraform/dynamodb_tables.json` matches (a test fails when they drift). There are no migrations; schema changes are additive attributes on Pydantic item models.
- **pytest:** Always pass `-n auto` for parallel execution. Tests use moto's in-memory DynamoDB — no services required.
- **New CRUD endpoints:** Extend `BaseDynamoEndpointRouter` + `BaseDynamoCRUDService`, then add the router to its domain's loader in `backend/app/composition/domains.py` with the prefix and tags it should carry. Both composition roots pick it up from there. A new route changes the routing table, so regenerate `backend/tests/fixtures/route_contract.json` and bump the count for that domain in `backend/tests/entrypoints/test_route_split.py`; the diff on the fixture is the review artifact.
- The backend CORS config explicitly allows `chrome-extension://` origins and `null` (for service workers).
