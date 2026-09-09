# CarModPicker migration inventory and proposed layout

Status: read-only inventory and proposal. No application code, Terraform, or
workflows were changed in the branch that carries this document.

This document records what the CarModPicker backend and frontend contain today,
proposes a per-domain package structure for the backend, and lists the Terraform,
platform module, and CI changes that the move implies. The decisions listed under
"Fixed decisions" below were agreed with the owner before this inventory was
written and are treated as constraints, not open options.

## Fixed decisions this proposal designs within

- The backend stays Python and FastAPI. It is restructured into per-domain
  packages, roughly 8 to 10 for this application, each owning its router,
  service, repository, and schemas. Business code must not know how it is hosted.
- There are two composition roots. One FastAPI application mounts every domain
  and serves local development, the test suite, and any future container. One
  entrypoint per domain serves the per-function deploy.
- The deploy unit is an OCI image per domain function, run on Lambda through the
  AWS Lambda Web Adapter with uvicorn, so that the identical image also runs on
  Fargate or App Runner. ECR is **one repository per domain per environment**,
  each with its own lifecycle rule, so `carmodpicker-staging-media` and
  `carmodpicker-prod-media` are separate repositories. That keeps a lifecycle
  rule from expiring another environment's images and keeps the pull policy on
  each repository scoped to the one account that runs it. Zip packaging goes
  away.
- API Gateway HTTP API routes by path prefix to the right domain function. The
  public API contract does not change and the frontend needs no edits. The
  migration follows the strangler pattern: routes move one domain at a time while
  the existing monolith keeps the `$default` route.
- Shared code moves to two new organisation repositories, one Python package and
  one TypeScript packages repository, published to AWS CodeArtifact. The core of
  each is framework-neutral. FastAPI and Lambda specifics live in small adapter
  sub-modules.
- Shared services, CodeArtifact among them, live in a **new WebbPulse Platform
  AWS account** that is being vended now. They do not live in Management.
  Production runs in the **member accounts**, account `734702670403` for this
  application. Management holds no workload and no shared service.
- Reusable GitHub workflows called through `workflow_call` in an organisation
  `.github` repository replace the per-application workflows.
- CloudWatch log retention becomes 7 days everywhere.
- Observability is OpenTelemetry, and it is the only instrumentation in the shared
  Python package. The default backends are AWS native: traces to X-Ray, structured
  JSON logs to CloudWatch at 7 day retention, and errors surfaced through a
  CloudWatch metric filter feeding the existing `api-alarms` module. A SaaS user
  interface is possible as an optional per-project OpenTelemetry exporter, never as
  the default. The Sentry SDK currently in CarModPicker is removed domain by domain
  as each domain moves onto the shared package, not in one sweep beforehand.
- The repository layer is the hard seam for the data store. DynamoDB stays.

## Summary of the current state

The backend is 24,090 lines under `backend/app`, spread over 25 endpoint modules,
25 DynamoDB tables, 25 repositories, and 15 services, exposing 176 HTTP routes.
That total is 162 `@router.<method>` decorators in the endpoint modules, plus 9
routes generated at runtime by `BaseDynamoEndpointRouter`, plus 5 root-level
routes in `main.py`. It was confirmed by importing the app and enumerating
`app.routes`, not by counting decorators, because the generated routes are
invisible to a decorator grep. It is deployed as a single Lambda zip behind one
HTTP API `$default` route, with `app/lambda_handler.py` a five-line Mangum
wrapper.

The frontend is 283 TypeScript files under `frontend/src`, about 41,400 source
lines plus 14,300 lines of colocated tests, on React 19, React Router 7, Tailwind
4, and Vitest.

Two facts shape most of the recommendations below. First, the platform modules
that a per-domain split needs have since been built and shipped for
WebbPulse-Portfolio, so the two blockers this document originally recorded are
closed; see the amendments section immediately below. Second, the genuine
cross-repository duplication with WebbPulse-Portfolio sits in the backend
plumbing and in the frontend tooling configuration, not in the frontend
application code.

Every count in this document was re-verified against the code after the first
draft. The route totals in particular come from importing the app and
enumerating `app.routes`, because three modules generate CRUD routes at runtime
that a decorator grep does not see. Where the first draft was wrong, the
corrected figure is used and the error is noted inline so the reasoning that
depended on it can be re-checked rather than silently inherited.

## 0. Amendments since this inventory was first written

WebbPulse-Portfolio was split into per-domain functions after this document was
drafted. That work closed several questions this inventory left open and proved
out the platform modules. Six corrections apply, and the body of the document
has been edited to match.

| Claim as originally written | Corrected |
|---|---|
| The shared Python package is named `webbpulse-core` | It is named `webbpulse`. The CodeArtifact domain is `webbpulse`, owner `432410731887`, repository `python` |
| The `lambda-function` module cannot deploy an OCI image | It can. `package_type` is derived from the `code` shape, `runtime` and `handler` accept `null`, `image_config` is exposed, and `image_uri` is on `ignore_changes` |
| The `http-api` module supports only one integration | It takes an `integrations` map and a `routes` map keyed by route key, plus `default_integration`. CarModPicker already consumes the fixed major version |
| A new ECR module is needed | An `ecr-repository` module exists and is in use |
| Alarms should extend the aggregate pattern to Lambda | `api-alarms` v2.1.0 does this through `lambda_function_names`, but the list is capped at ten functions. Nine domains plus the monolith is exactly ten, so the ceiling is reached on the last cut. See the split plan |
| Nothing said about the base image | The shared base image is pinned by digest: `432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7` |

Two further facts from the Portfolio work are recorded in
`docs/migration/container-image-workflow-gaps.md` in that repository and are
carried into the split plan rather than repeated here: the CodeArtifact token
must reach the build as a BuildKit secret mount and never as a build argument,
and `environment:` is not legal on a job that carries `uses:`, which is why the
`resolve-env` job pattern exists.

One correction of the opposite kind. CarModPicker's API prefix is `/api`, not
`/api/v1`. Every route key in the API Gateway `routes` map differs from
Portfolio's by that one segment, and the difference is easy to copy wrong.

---

---

## 1. Backend inventory

Classification key:

- **neutral** means framework-neutral and shareable, no FastAPI or Lambda import.
- **fastapi** means shareable but a FastAPI adapter.
- **lambda** means shareable but a Lambda or AWS-hosting adapter.
- **app** means CarModPicker-specific and stays in this repository.

The proposed shared package is named `webbpulse` in the new Python package
repository. Module paths below are inside that distribution.

### Core, configuration, and observability

| Path | Lines | What it does | Class | Proposed shared module | Duplicated in Portfolio |
|---|---|---|---|---|---|
| `app/core/config.py` | 318 | pydantic-settings `Settings`, origin parsing, secret field application | fastapi | `webbpulse_core.config` base class, app subclasses it | Yes, `app/config.py` (84), same idea, different code |
| `app/core/secrets.py` | 50 | Reads one `APP_SECRETS_ARN` JSON secret, exports keys into `os.environ` | lambda | `webbpulse_core.aws.secrets` | Yes, `app/secrets.py` (89), same idea, different code |
| `app/core/logging.py` | 104 | stdlib logging config, JSON formatter, colourised levels | neutral | `webbpulse_core.otel.logging`, rebuilt on the OpenTelemetry logging bridge | Partly, `app/core/logging.py` (5) uses Powertools instead |
| `app/core/log_context.py` | 34 | `ContextVar` request id and user id, logging filter | neutral | Replaced by OpenTelemetry context; trace and span id become the correlation keys, user id stays a span attribute | Same concept, Powertools does it in Portfolio |
| `app/core/sentry.py` | 146 | Sentry SDK 2.x init, env gates, scope processor from log context | app, being removed | None. Deleted per domain as each moves onto the shared package | No, Portfolio has no Sentry |
| `app/core/cloudwatch_emf.py` | 133 | EMF metric emitter for crawler runs | app | None. Crawler-specific, superseded by OpenTelemetry metrics | No |
| `app/core/email.py` | 122 | SESv2 `send_email`, loads rendered React Email HTML | lambda | `webbpulse_core.aws.ses` for transport; templates stay app | No |
| `app/core/car_inference.py` | 3,538 | Infers car make, model, generation from free text | app | n/a | No |
| `app/core/category_inference.py` | 998 | Infers part category from text | app | n/a | No |
| `app/core/init_cars.py` | 158 | Seeds car generations at startup | app | n/a | No |
| `app/core/init_categories.py` | 59 | Seeds categories | app | n/a | No |
| `app/core/car_generations.py` | 37 | Lazy JSON loader for generation data | app | n/a | No |
| `app/core/car_generations_data.py` | 125 | Seed data | app | n/a | No |
| `app/core/part_categories_data.py` | 117 | Seed data | app | n/a | No |

`car_inference.py` and `category_inference.py` together are 4,536 lines, nearly a
fifth of the backend, and belong to one domain. They are pure functions over text
and have no AWS or FastAPI dependency, so they are the easiest large block to
isolate even though they are not shareable across applications.

### Data access

| Path | Lines | What it does | Class | Proposed shared module | Duplicated in Portfolio |
|---|---|---|---|---|---|
| `app/db/dynamo/repository.py` | 507 | `DynamoRepository[TModel]` generic CRUD, query, batch, transactions | neutral | `webbpulse_core.dynamo.repository` | Yes, `app/db/repository.py` (372), same idea, untyped there |
| `app/db/dynamo/serialization.py` | 123 | Pydantic to DynamoDB item encoding, Decimal, datetime, bytes | neutral | `webbpulse_core.dynamo.serialization` | Yes, `app/db/serializer.py` (58), same idea, smaller |
| `app/db/dynamo/tables.py` | 320 | `TableSpec` and `IndexSpec` types plus all 25 table definitions | mixed | Types to `webbpulse_core.dynamo.spec`; the 25 definitions stay app | Yes for the types, `app/db/tables.py` (86) |
| `app/db/dynamo/client.py` | 62 | boto3 resource factory, table handle cache, `check_db_ready` | neutral | `webbpulse_core.dynamo.client` | Yes, `app/db/client.py`, same idea |
| `app/db/dynamo/models.py` | 26 | `DynamoModel`, `TimestampedDynamoModel`, uuid7 and utc helpers | neutral | `webbpulse_core.dynamo.models` | Partly |
| `app/db/dynamo/errors.py` | 30 | `DynamoError`, `ItemNotFound`, `ConditionFailed`, `TransactionCanceled` | neutral | `webbpulse_core.dynamo.errors` | Partly, `UniqueViolation` in Portfolio's repository |
| `app/db/dynamo/search.py` | 105 | In-memory scan-and-filter search helper | app | n/a | No |
| `app/db/dynamo/users.py` | 252 | User, OAuthAccount, WebAuthnCredential models and repositories | app | n/a | No |
| `app/db/dynamo/catalog.py` | 475 | Car, category, retailer, manufacturer, part, listing, price repositories | app | n/a | No |
| `app/db/dynamo/build_lists.py` | 221 | Build list, part, phase, labor estimate repositories | app | n/a | No |
| `app/db/dynamo/build_logs.py` | 88 | Build log and post repositories | app | n/a | No |
| `app/db/dynamo/moderation.py` | 221 | Vote and Report repositories, polymorphic `entity_key` | app | n/a | No |
| `app/db/dynamo/bug_reports.py` | 73 | Bug report repository | app | n/a | No |
| `app/db/dynamo/part_price_alerts.py` | 71 | Price alert repository | app | n/a | No |
| `app/db/dynamo/image_source_mappings.py` | 49 | Image dedup by canonical source URL | app | n/a | No |
| `app/db/dynamo/app_settings.py` | 47 | Singleton settings item | app | n/a | No |

The repository layer is the agreed seam for the data store, so the generic half
moving to `webbpulse` matters more than its line count suggests. It is also
the single largest genuine duplication with Portfolio.

### API plumbing

| Path | Lines | What it does | Class | Proposed shared module | Duplicated in Portfolio |
|---|---|---|---|---|---|
| `app/api/utils/response_patterns.py` | 477 | Standard success and error envelopes, raise helpers | fastapi | `webbpulse_core.fastapi.responses` | Loosely, Portfolio raises `HTTPException` inline |
| `app/api/utils/endpoint_decorators.py` | 291 | Decorators adding consistent response docs and error handling | fastapi | `webbpulse_core.fastapi.decorators` | No |
| `app/api/utils/base_dynamo_endpoint_router.py` | 159 | Generic CRUD router over `BaseDynamoCRUDService` | fastapi | `webbpulse_core.fastapi.crud_router` | Yes, `app/api/v1/crud_router.py` (80), independently invented |
| `app/api/utils/endpoint_registry.py` | 157 | Standardised router registration and prefix derivation | fastapi | `webbpulse_core.fastapi.registry` | No |
| `app/api/utils/pagination_utils.py` | 83 | Offset pagination params and envelope | fastapi | `webbpulse_core.fastapi.pagination` | Loosely, `limit`/`offset` in `crud_router` |
| `app/api/utils/cursor_pagination.py` | 81 | Opaque base64 cursor encode, decode, in-memory paginate | neutral | `webbpulse_core.pagination.cursor` | No |
| `app/api/utils/common_patterns.py` | 101 | Shared dependencies, ownership and admin checks, paged envelope | fastapi | Split: generic half to `webbpulse_core.fastapi.deps` | No |
| `app/api/utils/authorization.py` | 123 | Ownership checks over build lists and parts | app | n/a | No |
| `app/api/utils/image_utils.py` | 64 | File key validation, presigned URL for a key | app | Thin wrapper over shared S3 helper | No |
| `app/api/utils/image_url_utils.py` | 62 | Canonicalises CDN image URLs for dedup | neutral | `webbpulse_core.web.image_urls` | No |
| `app/api/utils/bucket_orphan_utils.py` | 45 | Collects referenced file keys for orphan cleanup | app | n/a | No |
| `app/api/utils/subscription_utils.py` | 36 | Premium tier and build list cap checks | app | n/a | No |
| `app/api/utils/google_oauth.py` | 82 | Google OAuth ID token verification | neutral | `webbpulse_core.auth.google_oauth` | No |
| `app/api/middleware/rate_limiter.py` | 282 | Per-method and per-endpoint rate limiting, in-memory, and trusts `X-Forwarded-For` | fastapi | `webbpulse_core.fastapi.rate_limit` over the shared `<prefix>-rate-limits` DynamoDB table, see the correctness note and decision below | Loosely, `core/login_limiter.py` (86) is login-only and DynamoDB-backed |
| `app/api/middleware/error_handler.py` | 243 | Converts exceptions to the standard error envelope | fastapi | `webbpulse_core.fastapi.errors` | No |
| `app/api/middleware/request_context.py` | 18 | Assigns a uuid7 request id, sets the context vars | fastapi | `webbpulse_core.fastapi.request_context` | Yes, `RequestLoggingMiddleware` in `core/middleware.py` |
| `app/api/dependencies/auth.py` | 197 | bcrypt hashing, JWT issue and verify, current-user dependencies | fastapi | `webbpulse_core.auth.passwords` and `.jwt` neutral, deps as adapter | Yes, `app/core/security.py` (76); PyJWT here, python-jose there |
| `app/api/dependencies/repositories.py` | 89 | Bundles all 25 repositories into one frozen dataclass singleton | app | n/a | No |
| `app/api/protocols.py` | 94 | Protocols for typing generic services | neutral | `webbpulse_core.protocols` | No |
| `app/main.py` | 372 | App factory, middleware, registers every router, health, ready, sitemap | app | Factory helper to `webbpulse_core.fastapi.app` | Yes for health and sitemap concepts |
| `app/lambda_handler.py` | 5 | Mangum adapter | lambda | Deleted, the Web Adapter replaces it | Yes, `app/lambda_handler.py` (13) with Powertools |

### Correctness finding: the rate limiter does not work on Lambda

Found while inventorying, unrelated to the restructure but worth fixing
independently of it. `SophisticatedRateLimiter` holds its counters in eight
`defaultdict` instances in process memory, a minute and an hour bucket for each
of the general, GET, auth, and admin classes. On Lambda every execution
environment gets its own instance, so counters are never shared between
concurrent environments and are lost on every cold start. The configured limits,
120 GET requests per minute and 10 auth requests per minute among them, are
therefore not actually enforced in production. Concurrency on these functions was
recently raised from 10 to 1000, which widens the gap by two orders of magnitude:
the effective limit is the configured limit multiplied by the number of live
execution environments.

There is a second bug in the same file. `_get_client_ip` takes the **leftmost**
hop of `X-Forwarded-For`:

```python
forwarded_for = request.headers.get("X-Forwarded-For")
if forwarded_for:
    return forwarded_for.split(",")[0].strip()
```

That value is caller-supplied and unverified. Any client can send
`X-Forwarded-For: <anything>` and get a fresh bucket per request, so even within
a single execution environment the limiter is trivially bypassed. This is the
more serious of the two defects, because the in-memory problem weakens the limit
while this one removes it.

### Decision: the rate limiting standard is layered

Locked, and it is a platform standard rather than a CarModPicker fix. Three
layers, each doing what it is actually good at.

**Layer 1, HTTP API stage and per-route throttling.** Free, enforced before any
Lambda is invoked, and already exposed by the platform `http-api` module through
`throttling_burst_limit` and `throttling_rate_limit` on the `$default` stage.
This is the blunt capacity guard that stops a flood from becoming a Lambda bill.
Per-route throttling on the expensive routes goes in alongside the
route-to-integration map that module change already needs.

**Layer 2, a per-identity fixed-window limiter in the shared Python package.**
This is the real limit, the one with per-identity semantics that API Gateway
cannot express. It lives in `webbpulse_core` and is backed by **one
`<prefix>-rate-limits` DynamoDB table with a TTL attribute**, one table per
environment, not one per domain. A fixed window is chosen over a sliding log
deliberately: it is a single conditional `UpdateItem` per request against one
item, where the current in-memory design keeps a list of timestamps per key.
It is applied to **auth routes and mutating routes**, not to every GET, which
keeps the added read and write cost proportionate to the risk.

It **fails open**. If the DynamoDB call errors or times out, the request is
served. A limiter that fails closed converts a partial DynamoDB problem into a
total outage, which is a worse failure than the one it prevents.

**Client identity is taken from the API Gateway request context**, specifically
the source IP that the Lambda Web Adapter forwards from
`requestContext.http.sourceIp`, **never from the leftmost `X-Forwarded-For`
hop**. API Gateway populates that field itself and a client cannot forge it.
This is the direct fix for the second bug above, and it is a hard rule for the
shared package: the header is never trusted as an identity source. Where a
request is authenticated, the user id is the better key and is used in
preference to the IP.

**Layer 3, CloudFront plus WAF, opt-in per project.** Rate-based WAF rules in
front of CloudFront handle volumetric and bot traffic. This is genuinely useful
and genuinely not free, so it is opt-in per project rather than part of the
baseline. CarModPicker does not need it today.

Portfolio's `core/login_limiter.py` is the closest existing thing to layer 2 and
is login-only; it is the starting point for the shared implementation rather
than a competing design. The in-memory limiter is not carried into the shared
package under any circumstances.

### Services

| Path | Lines | What it does | Class | Duplicated in Portfolio |
|---|---|---|---|---|
| `app/api/services/storage_service.py` | 742 | S3 upload, presign, delete, orphan listing, Pillow processing | mixed | No |
| `app/api/services/part_listing_service.py` | 523 | Listing upsert, price observation, retailer resolution | app | No |
| `app/api/services/part_service.py` | 458 | Part CRUD, filters, dedup, purge of related rows | app | No |
| `app/api/services/page_parser.py` | 390 | JSON-LD, OpenGraph, DOM product extraction | neutral | No |
| `app/api/services/part_price_aggregation_service.py` | 326 | Rolls listings into price summaries | app | No |
| `app/api/services/report_service.py` | 231 | Polymorphic content reports | app | No |
| `app/api/services/vote_service.py` | 225 | Polymorphic voting with score denormalisation | app | No |
| `app/api/services/part_price_alert_service.py` | 224 | Threshold checks, fires SES price-drop email | app | No |
| `app/api/services/sitemap_service.py` | 221 | Sitemap index and child sitemap XML | neutral | Yes, `app/api/seo.py` (58), same idea |
| `app/api/services/car_generation_service.py` | 168 | Make, model, generation resolution | app | No |
| `app/api/services/build_list_service.py` | 157 | Build list CRUD, free-tier cap, build log creation, copy | app | No |
| `app/api/services/bug_report_service.py` | 160 | Bug report lifecycle | app | No |
| `app/api/services/base_dynamo_crud_service.py` | 102 | Generic CRUD service backing the generic router | fastapi | Yes, folded into Portfolio's `crud_router` |
| `app/api/services/page_html_sanitizer.py` | 86 | Strips scripts and user state from submitted DOM | neutral | No |
| `app/api/services/user_service.py` | 79 | User creation, OAuth account linking | app | No |

`storage_service.py` is the one service worth splitting rather than classifying
whole. The S3 client wiring, presigning, and key handling are reusable, while the
Pillow processing and the CarModPicker bucket conventions are app-specific.

### Endpoints

All 25 endpoint modules are app-specific. Their route counts feed section 2.
The Routes column is the decorator count. Three modules also mount a
`BaseDynamoEndpointRouter`, which attaches up to six generic CRUD routes that no
decorator declares; the Generated column is what each actually contributes after
its `disable_endpoints` list is applied.

| Path | Lines | Routes | Generated | Total |
|---|---|---|---|---|
| `app/api/endpoints/parts.py` | 596 | 18 | 3 | 21 |
| `app/api/endpoints/build_lists.py` | 673 | 15 | 3 | 18 |
| `app/api/endpoints/users.py` | 577 | 12 | 0 | 12 |
| `app/api/endpoints/build_list_parts.py` | 566 | 10 | 0 | 10 |
| `app/api/endpoints/part_manufacturers.py` | 240 | 10 | 0 | 10 |
| `app/api/endpoints/images.py` | 431 | 8 | 0 | 8 |
| `app/api/endpoints/reports.py` | 237 | 8 | 0 | 8 |
| `app/api/endpoints/auth/core.py` | 294 | 7 | 0 | 7 |
| `app/api/endpoints/auth/oauth.py` | 425 | 7 | 0 | 7 |
| `app/api/endpoints/auth/webauthn.py` | 319 | 7 | 0 | 7 |
| `app/api/endpoints/bug_reports.py` | 216 | 7 | 0 | 7 |
| `app/api/endpoints/car_generations.py` | 156 | 7 | 3 | 10 |
| `app/api/endpoints/retailers.py` | 185 | 7 | 0 | 7 |
| `app/api/endpoints/build_logs.py` | 278 | 5 | 0 | 5 |
| `app/api/endpoints/categories.py` | 90 | 5 | 0 | 5 |
| `app/api/endpoints/part_price_alerts.py` | 222 | 5 | 0 | 5 |
| `app/api/endpoints/votes.py` | 156 | 5 | 0 | 5 |
| `app/api/endpoints/admin/db_ops.py` | 237 | 5 | 0 | 5 |
| `app/api/endpoints/auth/two_factor.py` | 158 | 3 | 0 | 3 |
| `app/api/endpoints/build_list_phases.py` | 120 | 3 | 0 | 3 |
| `app/api/endpoints/build_list_labor_estimates.py` | 127 | 3 | 0 | 3 |
| `app/api/endpoints/app_settings.py` | 52 | 2 | 0 | 2 |
| `app/api/endpoints/search.py` | 103 | 1 | 0 | 1 |
| `app/api/endpoints/crawled_pages.py` | 176 | 1 | 0 | 1 |
| `app/api/endpoints/admin/stats.py` | 52 | 1 | 0 | 1 |

The 22 modules under `app/api/schemas/` (1,535 lines total) are all
app-specific request and response models, except `pagination.py` (11 lines),
whose `CursorPage` envelope moves with the cursor pagination helper.

### Duplication with WebbPulse-Portfolio, summarised

Portfolio's backend is 6,479 lines including tests, far smaller, but it
independently reimplements the same plumbing. The clearest cases:

| Concern | CarModPicker | Portfolio | Similarity |
|---|---|---|---|
| Generic Dynamo repository | `db/dynamo/repository.py` 507 | `db/repository.py` 372 | Same idea, different code. CarModPicker is `Generic[TModel]`, Portfolio is untyped |
| Item serialization | `db/dynamo/serialization.py` 123 | `db/serializer.py` 58 | Same idea, CarModPicker handles more types |
| Generic CRUD router | `utils/base_dynamo_endpoint_router.py` 159 | `api/v1/crud_router.py` 80 | Same idea, independently invented |
| Secrets loading | `core/secrets.py` 50 | `secrets.py` 89 | Same contract, one `APP_SECRETS_ARN` JSON secret. CarModPicker writes `os.environ`, Portfolio caches in module scope |
| Settings | `core/config.py` 318 | `config.py` 84 | Same pattern, pydantic-settings plus secret fields |
| Password and JWT | `dependencies/auth.py` 197 | `core/security.py` 76 | Same idea, PyJWT versus python-jose, a real conflict to resolve |
| Request id logging | `middleware/request_context.py` 18 | `core/middleware.py` 68 | Same idea, Powertools versus stdlib |
| Sitemap | `services/sitemap_service.py` 221 | `api/seo.py` 58 | Same idea, CarModPicker adds a sitemap index |
| Table spec types | `db/dynamo/tables.py` types | `db/tables.py` 86 | Same concept, different shape |

Two more near-identical pairs worth naming: the DynamoDB client (62 lines here,
32 there) is the same boto3 resource singleton with the same local-endpoint
override and test reset hook, and the CORS block in each `main.py` is
near-identical, both setting `allow_credentials=True` with explicit method and
header allowlists.

CarModPicker-only, with no Portfolio counterpart, so these enter the shared
package on CarModPicker's terms alone: SES send, cursor pagination, response
patterns and the error envelope, typed Dynamo errors, endpoint decorators and
registry, Google OAuth verification, image URL canonicalisation, S3 storage
helpers, model bases, protocols, page parsing, and HTML sanitisation. Adding
these to Portfolio is a decision to give it new capability, which is a different
decision from removing duplication and should be scoped separately.

The extraction splits into three tiers by difficulty rather than by line count.

**Tier 1, extract as-is.** Near-identical and genuinely framework-neutral: the
secrets loader, DynamoDB client, serialization, settings base, CORS block, and
the health and ready probe. The Mangum wiring is near-identical too but is
deleted rather than shared, since the Web Adapter replaces it.

**Tier 2, converge first.** The generic repository, table specs, and generic CRUD
router are the same concept at incompatible maturity. The repository pair reads
as the biggest win by line count, 507 plus 372, but CarModPicker is built on
Pydantic models with uuid7 ids while Portfolio uses plain dicts with an integer
counter table. Sharing means Portfolio adopting CarModPicker's data model and
migrating its rows. That is a data migration, not a code extraction, and it must
be scoped on its own rather than folded into the shared-package work.

**Tier 3, not duplication.** Everything in the CarModPicker-only list above.

One conflict must still be settled before the shared auth module is cut: PyJWT
here versus python-jose in Portfolio. The logging conflict is now resolved by the
observability decision, since both stacks are replaced by OpenTelemetry rather
than one being chosen over the other.

---

## 2. Proposed domain boundaries

Nine domains. The Routes column is the real route count per domain, decorators
plus the routes `BaseDynamoEndpointRouter` generates, totalling 171 across the
endpoint modules. Table names are unprefixed; at runtime they carry
`carmodpicker-<env>-`.

The write sets below are the tables a domain writes **through its own request
paths today**, including the cascades and denormalisations its services perform
into other domains' tables. They are deliberately not the tidy "one domain owns
its tables" picture, because that picture is not what the code does. Section 2's
cross-domain subsection and the async event decision in section 2.1 are what
close the gap.

| Domain | Endpoint modules | Routes | Tables read | Tables written | AWS services | Minimum IAM |
|---|---|---|---|---|---|---|
| `identity` | `auth/core`, `auth/oauth`, `auth/two_factor`, `auth/webauthn` | 24 | users, oauth_accounts, webauthn_credentials | users, oauth_accounts, webauthn_credentials | DynamoDB, SES, Secrets Manager | Dynamo CRUD on 3 tables and their indexes, `ses:SendEmail` on the identity and config set, `secretsmanager:GetSecretValue` on the app secret |
| `users` | `users`, `app_settings` | 14 | users, app_settings, build_lists, build_list_parts, build_list_phases, build_list_labor_estimates, build_logs, build_log_posts, parts, votes, reports, part_price_alerts, oauth_accounts, webauthn_credentials | users, app_settings, and via the delete cascade oauth_accounts, webauthn_credentials, build_lists, build_list_parts, build_list_phases, build_list_labor_estimates, build_logs, build_log_posts, parts, part_cars, part_listings, part_price_history, part_price_alerts, votes, reports | DynamoDB, S3 read and write, Secrets Manager | Dynamo read on 14 tables; write on 2 in steady state, 16 during the cascade until it goes async; `s3:PutObject`, `GetObject`, `DeleteObject` for avatars; `secretsmanager:GetSecretValue` |
| `catalog` | `parts`, `part_manufacturers`, `categories`, `retailers` | 43 | parts, part_cars, part_listings, part_price_history, part_manufacturers, categories, retailers, car_makes, car_models, car_generations, build_list_parts, votes, reports, part_price_alerts | parts, part_cars, part_listings, part_price_history, part_manufacturers, categories, retailers, and via the part purge build_list_parts, votes, reports, part_price_alerts | DynamoDB, S3 read and delete, SES, Secrets Manager | Dynamo CRUD on 7 tables plus read on 7 and purge writes on 4; `s3:GetObject`, `DeleteObject`; `ses:SendEmail` for the price-drop path; `secretsmanager:GetSecretValue` |
| `vehicles` | `car_generations`, `search` | 11 | car_makes, car_models, car_generations, build_lists, users | none | DynamoDB, Secrets Manager | Dynamo read only, on 5 tables; `secretsmanager:GetSecretValue` |
| `build-lists` | `build_lists`, `build_list_parts`, `build_list_phases`, `build_list_labor_estimates` | 34 | build_lists, build_list_parts, build_list_phases, build_list_labor_estimates, parts, categories, retailers, car_generations, votes | build_lists, build_list_parts, build_list_phases, build_list_labor_estimates, build_logs, part_listings, part_price_history | DynamoDB, S3 read and delete, SES, Secrets Manager | Dynamo CRUD on 4 tables, write on 3 more, read on 5; `s3:GetObject`, `DeleteObject`; `ses:SendEmail` for the price-drop path; `secretsmanager:GetSecretValue` |
| `build-logs` | `build_logs` | 5 | build_logs, build_log_posts, build_lists, users | build_logs, build_log_posts | DynamoDB, Secrets Manager | Dynamo CRUD on 2 tables, read on 2; `secretsmanager:GetSecretValue` |
| `moderation` | `votes`, `reports`, `bug_reports` | 20 | votes, reports, bug_reports, build_lists, parts, users, car_generations | votes, reports, bug_reports, parts (`net_votes` only) | DynamoDB, Secrets Manager | Dynamo CRUD on 3 tables, read on 4, and a narrow `UpdateItem` on `parts.net_votes`; `secretsmanager:GetSecretValue` |
| `media` | `images` | 8 | image_source_mappings, build_lists, parts | image_source_mappings | DynamoDB, S3 read, write and delete, Secrets Manager | Dynamo CRUD on 1 table plus read on 2, `s3:PutObject`, `GetObject`, `DeleteObject`, `HeadObject`, `ListBucket`; `secretsmanager:GetSecretValue` |
| `ingestion` | `crawled_pages`, `part_price_alerts`, `admin/db_ops`, `admin/stats` | 12 | most tables, admin operations are broad | part_price_alerts, and from `admin/db_ops` car_makes, car_models, car_generations, part_manufacturers, parts, part_cars, build_lists, votes | DynamoDB, Secrets Manager | Broad Dynamo access for the admin operations; `secretsmanager:GetSecretValue`. No SES and no S3: see the note below |

Total: 24 + 14 + 43 + 11 + 34 + 5 + 20 + 8 + 12 = 171 routes from the endpoint
modules, plus the 5 root-level routes in `main.py` (`/`, `/health`, `/ready`,
`/sitemap.xml`, `/sitemap-{name}.xml`) which every function serves locally for its
own health checks, for 176 in total. FastAPI additionally mounts `/docs`,
`/docs/oauth2-redirect`, `/redoc`, and `/api/openapi.json`, which are excluded
from every count here.

Three corrections to the naive decorator count are worth calling out, because
each one moves a domain's size. `parts`, `build_lists`, and `car_generations`
each mount a `BaseDynamoEndpointRouter` that attaches generic CRUD routes no
decorator declares, three each after their `disable_endpoints` lists are applied.
That is why `catalog` is 43 and not 40, `build-lists` 34 and not 31, and
`vehicles` 11 and not 8. Any contract test that locks the route set must import
the app rather than grep for decorators, or it will silently miss nine routes.

### Why these merges

**`identity` merges the four auth modules.** They are one deployable concern,
they share the same three tables, and `oauth.py` and `webauthn.py` both mutate
the user record. Splitting them would put a write to `users` behind two
functions.

**`users` keeps `app_settings`.** `app_settings` is two routes over a singleton
item, and the premium kill switch it holds is read by the subscription checks
that live in the user profile path. A separate function for two routes is not
worth a cold start.

**`catalog` merges parts, manufacturers, categories, and retailers.** This is the
largest domain at 40 routes and it is deliberate. `part_service.py` touches 12
repositories, and manufacturers, categories, and retailers are all foreign keys
resolved during part read and write. Splitting them would turn the hot part-list
path into three network calls. The car inference modules, 4,536 lines, are pulled
in here as a library rather than a service.

**`vehicles` merges `car_generations` with `search`.** Search is one route that
fans out over build lists, users, and parts. It is placed with vehicles because
`search.py` already imports `car_generation_service`, and vehicles is otherwise
the smallest domain. This is the weakest boundary in the set and is called out as
an open question in section 6. Worth noting that `vehicles` is entirely
read-only: `CarGenerationService` has no create, update, or delete. The car seed
writes live in `app/core/init_cars.py`, which runs from the `main.py` lifespan
under `RUN_STARTUP_TASKS`, and in `admin/db_ops`. That startup task needs a home
in the new layout: running it in all nine functions would have nine cold starts
racing the same seed writes, so it should move to a one-off job or be gated to a
single function.

**`build-lists` merges the list with its parts, phases, and labor estimates.**
The three child modules are meaningless without the parent, all three check
ownership through the parent build list, and `build_list_phases.py` already reads
labor estimates and parts to cascade deletes.

**`moderation` merges votes, reports, and bug reports.** Votes and reports are
already polymorphic over `entity_type` and `entity_id` and share the same
`entity_key` index shape. Bug reports join them as another user-submitted
moderation queue with the same status index pattern.

**`media` is only 8 routes but stays separate.** The original reason given for
this split, that it is the only domain needing S3 write, does not survive
checking: `users` uploads and deletes avatars, and `catalog` and `build-lists`
both call `delete_image`, so four domains need S3 write or delete today. What
still justifies the split is narrower but real. `media` is the only domain that
needs `ListBucket` and the bulk object operations behind the admin orphan
cleanup, and it is the only one whose S3 access is its entire purpose rather than
an incidental side effect of an entity write. Keeping it separate lets the other
three hold `PutObject` and `DeleteObject` scoped to their own key prefixes while
`media` alone holds the bucket-wide grants.

**`ingestion` collects the Chrome extension scrape endpoint, price alerts, and
the admin operations.** These are the low-traffic, mostly machine-driven paths,
and they have very different scaling and timeout profiles from the interactive
read paths. Admin operations are grouped here rather than given their own
function because they are rare and already privileged.

One correction to how this domain was originally described. It is not the
write-heavy ingestion path it sounds like. `crawled_pages.py` touches no
repository at all: it sanitises and parses HTML and returns the result, and the
caller writes. The listing and price-history writes that look like ingestion are
performed by `part_listing_service`, which is invoked from `parts.py`,
`build_list_parts.py`, and `part_manufacturers.py`, so they belong to `catalog`
and `build-lists`. The SES price-drop email fires from the same path, which is
why those two domains carry `ses:SendEmail` in the table above and `ingestion`
does not. What is genuinely left in `ingestion` is the price-alert CRUD and the
broad admin operations. That makes it a thinner and more privilege-heavy domain
than the name suggests, and it is a reasonable candidate to rename `admin` or to
fold its two alert routes into `catalog`. Noted as an open question in section 6.

### Cross-domain calls

The coupling map was taken from the repository names each endpoint and service
module references. It divides into three kinds.

**Becomes an in-process import, no change needed.** Calls that stay inside one
domain after the split: `build_lists` to its phases, parts, and labor estimates;
`parts` to listings and retailers; `auth/oauth` to users; `votes` to reports.

**Becomes a read of another domain's table, allowed by policy.** Several domains
read tables they do not own, purely to denormalise a display value: `build-logs`
reads `users` for author names, `build-lists` reads `parts` and `car_generations`
for display, `moderation` reads `build_lists` and `parts` to render the reported
entity. The proposal is to allow cross-domain reads at the repository layer with
read-only IAM, rather than introduce service-to-service HTTP calls. This keeps
latency flat and is the pragmatic reading of "the repository layer is the hard
seam".

**Needs rethinking before the cut.** Three cases write across domain boundaries.
All three are settled by the same decision, recorded in section 2.1.

1. `users.py` touches 13 repositories, almost all of them to build the profile
   aggregate and to cascade a user delete. Verified against
   `_delete_user_everywhere` in `endpoints/users.py`, the delete writes into
   `oauth_accounts`, `webauthn_credentials`, `build_lists`, `build_list_parts`,
   `build_list_phases`, `build_list_labor_estimates`, `build_logs`,
   `build_log_posts`, `parts`, `part_price_alerts`, `votes`, and `reports`, and
   transitively into `part_cars`, `part_listings`, and `part_price_history`
   through the part purge. That is tables owned by five other domains, not four,
   and it is the single hardest item in the migration.
2. `part_service.purge_related_rows_for_parts` writes to `build_list_parts`,
   `votes`, `reports`, and `part_price_alerts`, which belong to three other
   domains. Same problem as the user cascade, smaller blast radius. Verified at
   `services/part_service.py:446-458`.
3. `vote_service` denormalises a score after every vote. The earlier draft of
   this document said it writes onto both `build_lists` and `parts`; that is
   wrong. `_sync_part_net_votes` early-returns unless the entity is a part, then
   writes `parts.net_votes` and nothing else. Build list scores are computed on
   read from the `votes` table. So this is one cross-domain write attribute, not
   two.

`admin/db_ops` and `admin/stats` legitimately span everything and are accepted as
a broad-permission function by design.

### 2.1 Decision: cross-domain writes go async through events

Locked. None of the three cases above is solved by granting one domain write
access to another's tables. Every cross-domain write becomes an asynchronous
event, and the owning domain is the only writer of its own tables.

The shape is the same in all three cases:

1. The domain that owns the originating entity writes a **tombstone** into its
   own table, in the same request, as the single durable record that the
   operation happened. A user delete writes a `deleted` marker on the user row
   rather than removing it; a part purge writes one on the part row.
2. **DynamoDB Streams** on that table, or an SQS queue the domain writes to,
   fans the event out to each other domain.
3. Each domain runs its **own cleanup handler** against **its own tables only**,
   subscribed to that event. `build-lists` deletes its own rows, `moderation`
   deletes its own votes and reports, and so on. No domain ever holds write IAM
   on a table it does not own.
4. The tombstone is reaped once every subscriber has acknowledged, or simply left
   in place with a TTL.

Vote score denormalisation works the same way. `moderation` writes the vote and
nothing else. The stream on the `votes` table drives a handler in `catalog` that
recomputes and writes `parts.net_votes`. `moderation` therefore drops the
`parts` write from its IAM entirely, and the row in the domain table above that
grants it a narrow `UpdateItem` on `net_votes` is an interim state, valid only
until this lands.

What this buys and what it costs. The IAM story becomes clean: write permission
per domain is exactly the tables that domain owns, which is what makes the
per-domain policies in `lambda.tf` worth writing at all. The cost is that the
cascade becomes eventually consistent, and every read path that could observe a
half-cleaned entity must tolerate it. In practice that means the tombstone must
be checked on read: a user marked deleted is not served, a purged part is not
listed, before the fan-out has finished. That check is a prerequisite for the
cut, not an afterthought, and it is the reason the `users` carve-out stays last
in the sequence.

The consequence for sequencing is that the event plumbing, the stream or queue,
the per-domain handlers, and the tombstone reads, is its own PR that must land
before the `users` and `catalog` carve-outs, not alongside them.

---

## 3. Proposed source layout

```
backend/
  pyproject.toml                 one distribution, many entrypoints
  src/
    carmodpicker/
      domains/
        identity/
          __init__.py
          router.py              APIRouter, no prefix knowledge
          service.py
          repository.py
          schemas.py
          app.py                 per-domain composition root
        users/                   same five files
        catalog/
          ...
          inference/             car_inference, category_inference live here
        vehicles/
        build_lists/
        build_logs/
        moderation/
        media/
        ingestion/
      shared/
        deps.py                  cross-domain read-only repository access
        settings.py              subclasses webbpulse_core.config
        tables.py                the 25 TableSpec definitions
        observability.py         calls webbpulse_core.otel.configure; holds the
                                 per-domain Sentry shim until that domain moves
      composition/
        monolith.py              root A: mounts every domain
        __init__.py
  entrypoints/
    identity.py                  root B: one per domain, each `from
    users.py                     carmodpicker.domains.<d>.app import app`
    catalog.py
    vehicles.py
    build_lists.py
    build_logs.py
    moderation.py
    media.py
    ingestion.py
  tests/
    unit/
      <domain>/                  service and repository tests, moto-backed
    contract/
      test_route_inventory.py    asserts the union of domain routers equals
                                 today's 176 routes and paths, the guard that
                                 the public contract did not move. It must
                                 enumerate app.routes, not grep decorators
    integration/
      <domain>/                  per-domain app, TestClient against moto
    monolith/                    the existing suite, repointed at composition.monolith
  docker/
    Dockerfile                   one file, DOMAIN build arg
```

Both composition roots import the same domain packages. `composition/monolith.py`
mounts all nine routers at their existing prefixes and is what `uvicorn` serves
locally, what the existing test suite runs against, and what a future single
container would run. Each `domains/<d>/app.py` builds a FastAPI app carrying only
that domain's router plus the shared middleware, health, and ready routes.

Route prefixes stay exactly where they are. `EndpointRegistry` currently derives
`/api/<entity>` from the entity name; that derivation moves into the shared
composition helper so both roots produce identical paths. The contract test above
is what proves it.

### Tests

The existing 97 test files and 26,690 lines run against the monolith root
unchanged, which is the safety net for the whole restructure. New per-domain
integration tests are added as each domain is extracted. `pytest -n auto` and the
moto-backed DynamoDB fixtures carry over untouched. The existing
`tests/db/test_dynamo_tables_json_up_to_date.py` guard still applies, since
`shared/tables.py` remains the single source for `terraform/dynamodb_tables.json`.

### Dockerfile sketch

One Dockerfile, parameterised by domain, so nine images come from one definition.

```dockerfile
# syntax=docker/dockerfile:1
ARG BASE=<account>.dkr.ecr.us-west-2.amazonaws.com/carmodpicker-base:1
FROM ${BASE} AS runtime

ARG DOMAIN
ENV DOMAIN=${DOMAIN} \
    PORT=8000 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/ready \
    AWS_LWA_INVOKE_MODE=buffered

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 \
     /lambda-adapter /opt/extensions/lambda-adapter

COPY src/ /app/src/
COPY entrypoints/ /app/entrypoints/
WORKDIR /app
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD exec uvicorn --host 0.0.0.0 --port ${PORT} \
      --workers 1 --no-access-log \
      entrypoints.${DOMAIN}:app
```

The same image runs on Fargate or App Runner unchanged: the Lambda adapter in
`/opt/extensions` is inert when there is no Lambda runtime API to talk to, and
uvicorn is already listening on the port those platforms expect.

**Shared base image.** The `BASE` argument points at a `carmodpicker-base` image
built from `requirements-lambda.txt`, holding the interpreter and every third
party dependency, including the heavy ones, Pillow, boto3, and the WebAuthn and
crypto libraries. The nine domain images then add only first-party source, so
each is small and each rebuild is fast. The base is rebuilt only when
dependencies change, which is also where the `webbpulse` package from
CodeArtifact is installed. Given nine images per deploy, this is the difference
between a rebuild that ships a few hundred kilobytes and one that ships hundreds
of megabytes nine times.

### Observability in the shared package

OpenTelemetry is the only instrumentation the shared package exposes. It sits in
`webbpulse_core` as a neutral core plus two thin adapters, matching the same
split used everywhere else:

```
webbpulse_core/
  otel/
    __init__.py        configure(service_name, resource_attrs) -> providers
    logging.py         JSON formatter on the OTel logging bridge; trace_id and
                       span_id become the correlation keys
    tracing.py         tracer provider, sampler, span helpers
    metrics.py         meter provider
    adapters/
      fastapi.py       FastAPIInstrumentor wiring, request span attributes
      lambda_.py       lazy init, see below; exporter selection per environment
```

Default backends are AWS native. Traces go to X-Ray, structured JSON logs to
CloudWatch at 7 day retention, and errors are surfaced by a CloudWatch metric
filter over the log group feeding the existing `api-alarms` module, so error
alerting reuses the SNS topic and subscriptions already in place rather than
adding a parallel path. A SaaS user interface, if any project wants one, is an
additional OpenTelemetry exporter configured per project. It is never the default
and never the only destination.

**Cold start cost, and why initialisation must be lazy.** Eagerly building the
OpenTelemetry SDK at import time is a real cold-start tax in a Lambda image:
constructing the tracer, meter, and logger providers, resolving the resource
detectors, and starting the batch span processor all happen before the first
request is served, and the AWS resource detectors in particular can attempt
network calls. Paying that on every cold start, now multiplied across nine
functions instead of one, is the wrong default.

The proposal is that `otel/adapters/lambda_.py` initialises lazily. The module
import registers nothing beyond a no-op tracer; the providers are built on first
span creation, behind a module-level guard so concurrent first requests build
them once. Resource detection is restricted to the environment variables Lambda
already sets, avoiding detector network calls entirely, and the exporter is
configured with an explicit endpoint rather than discovered. Under the Web
Adapter the process is a long-lived uvicorn server rather than a per-invocation
handler, so the initialisation cost is paid once per execution environment and
then amortised across every request that environment serves, which makes lazy
init strictly better here than it would be under the old Mangum handler.

The Sentry SDK is removed one domain at a time, as each domain moves onto the
shared package. Until a given domain has moved, it keeps `core/sentry.py` and
keeps reporting to Sentry, so there is never a window where a domain has no error
reporting at all. `core/sentry.py` is deleted only after the last domain is
converted, and `lib/sentry.ts` on the frontend is a separate decision that this
document does not settle.

---

## 4. Frontend inventory

The proposed TypeScript packages repository is `webbpulse-web`, published to
CodeArtifact under the `@webbpulse` scope.

| Area | Files | Lines | Class | Proposed package | Notes |
|---|---|---|---|---|---|
| `src/components/ui/` | 19 | 1,587 | shareable | `@webbpulse/ui` | shadcn-style over Radix, CVA, and `cn()`. Only `status-badge.tsx` leaks, importing app constants |
| `src/components/forms/` | 2 | 641 | shareable | `@webbpulse/ui` | `SearchableSelect` fully generic, `ImageUpload` generic apart from an entity-type contract |
| `src/components/tables/` | 1 | 43 | shareable | `@webbpulse/ui` | pairs with `useResponsiveColumns` |
| `src/components/images/ImageWithPlaceholder.tsx` | 1 | 71 | shareable | `@webbpulse/ui` | generic img with fallback |
| `src/components/layout/` PageHeader, SectionHeader, Divider | 3 | 47 | shareable | `@webbpulse/ui` | rest of `layout/` is app-specific |
| `src/components/auth/` | 3 | 64 | shareable | `@webbpulse/ui` | generic form scaffolding, named for the auth pages |
| `src/components/routes/` | 4 | 173 | shareable | `@webbpulse/react` | `ProtectedRoute`, `GuestRoute`, `RouteGroupBoundary` |
| `src/components/shell/ErrorBoundary.tsx` | 1 | n/a | shareable | `@webbpulse/react` | class-based root boundary |
| `src/hooks/UseApiRequest.tsx` | 1 | 73 | shareable | `@webbpulse/react` | the de facto error-handling layer, `parseApiError` unpacks FastAPI validation errors |
| `src/hooks/useContainerWidth.ts` | 1 | 40 | shareable | `@webbpulse/react` | ResizeObserver primitive |
| `src/hooks/useResponsiveColumns.ts` | 1 | 52 | shareable | `@webbpulse/react` | column dropping by priority |
| `src/hooks/useCookieConsent.ts` | 1 | 94 | shareable | `@webbpulse/react` | localStorage plus custom event |
| `src/hooks/useDocumentMeta.ts` | 1 | 82 | shareable with config | `@webbpulse/react` | mechanism generic, site name hardcoded, needs a config prop |
| `src/hooks/useAuth.ts` | 1 | 11 | shareable | `@webbpulse/react` | context consumer with guard |
| `src/api/client.ts` | 1 | 143 | shareable with care | `@webbpulse/http` | see the caveat below |
| `src/contexts/AuthContext*.tsx` | 2 | 114 | app-specific shape | `@webbpulse/react` if generalised | bound to `/users/me` and `UserRead` |
| `src/lib/utils.ts` | 1 | 6 | shareable | `@webbpulse/ui` | `cn()` = clsx plus tailwind-merge |
| `src/lib/sentry.ts` | 1 | 72 | open | `@webbpulse/observability` | The backend observability decision covers the Python package only. Whether the browser moves to OpenTelemetry or keeps Sentry is a separate call, noted in section 6 |
| eslint flat config | 1 | ~100 | shareable | `@webbpulse/eslint-config` | typed-checked rules, plus a `no-restricted-imports` gate for retired primitives |
| `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` | 3 | n/a | shareable | `@webbpulse/tsconfig` | `tsconfig.json` is byte-identical to Portfolio's |
| `vite.config.ts` | 1 | ~50 | shareable as a factory | `@webbpulse/vite-config` | port and proxy differ per app, Sentry plugin is CI-gated |
| `vitest.config.ts` | 1 | ~30 | shareable as a factory | `@webbpulse/vite-config` | coverage thresholds 60/60/50/50 are enforced |
| Tailwind | 0 | n/a | shareable as tokens | `@webbpulse/tokens` | v4, CSS-first. No JS config exists; the tokens live in `src/styles/tokens.css` |
| `.prettierrc.json` | 1 | n/a | shareable | `@webbpulse/prettier-config` | CarModPicker's 6 keys are a strict subset of Portfolio's 10 |
| `src/api/*.ts` (21 domain modules) | 21 | ~1,743 | app-specific | n/a | thin wrappers per backend domain, one test file each |
| `src/pages/`, `src/components/parts|buildLists|buildListParts|cars|filters|profile|admin|ads|users` | ~130 | ~34,000 | app-specific | n/a | |
| `src/types/Api.ts` | 1 | 710 | app-specific | n/a | could be generated from the OpenAPI schema instead |
| `src/services/Api.ts` | 1 | 28 | delete | n/a | self-described temporary re-export shim over `src/api/*`, still imported by 53 non-test source modules |

### The API client caveat

`api/client.ts` carries two details that must survive any extraction: it sets
`withCredentials: true`, required by the staging CloudFront signed-cookie access
gate, and it uses a custom `paramsSerializer` that repeats keys for array values
rather than bracket-encoding them, which the backend's `ids` and `category_ids`
parameters depend on. Its 401 branch is currently dead code, the redirect is
commented out, so 401 handling in practice happens in `AuthContext` and the route
guards.

Extracting it is harder than the line count suggests. CarModPicker uses axios and
rejects the promise on error; Portfolio uses `fetch` and swallows every error,
returning `{data: null, error}`. A shared client forces one application to change
at every call site. The recommendation is to ship `@webbpulse/http` shaped like
CarModPicker's contract and migrate Portfolio to it deliberately, not to find a
compromise that suits neither.

### Frontend duplication with Portfolio

Outside the configuration files this is largely not duplication. It is two
independent implementations of the same concepts at very different maturity, so
most shared frontend work is a rewrite plus a migration rather than an
extraction. Specifically: `tsconfig.json` is byte-identical and `tsconfig.node.json`
differs only in string casing, `.prettierrc` is a near-subset, and those are the
real near-term wins. Against that, Tailwind v4 here versus v3 in Portfolio blocks
sharing anything that emits classes, including the whole UI kit; the two Button
implementations have diverged completely (CVA and Radix here, string concatenation
there); there is no auth context in Portfolio at all, it uses inline `useState`;
the token keys differ, `access_token` versus `authToken`; and there is zero hook
name overlap.

Two things worth noting before any frontend extraction starts. Portfolio's
frontend has exactly one test file, against about 90 here, so extraction has no
regression net on that side. And Portfolio's `src/hooks/useApiData.ts` is eight
hand-copies of the same 30-line fetch block, collapsible to roughly 40 lines with
one generic hook; that same-repo cleanup should precede any cross-repo work.

Minor packaging note found while inventorying: `eslint-plugin-react-dom` and
`eslint-plugin-react-x` are in `dependencies` rather than `devDependencies`, so
they ship in the production tree, and both repositories still carry `autoprefixer`
and `postcss` although Tailwind v4 through the Vite plugin no longer needs a
PostCSS pipeline.

---

## 5. Terraform and CI impact

### Files in `terraform/` that change

| File | Lines | Change |
|---|---|---|
| `lambda.tf` | 142 | Largest change. One `module "lambda_api"` becomes nine image-based functions, most naturally a `for_each` over a domains map. The four inline `aws_iam_role_policy` resources become per-domain policies scoped to the tables in section 2 instead of the current wildcard `table/carmodpicker-<env>-*`. `archive_file` and the `lambda_placeholder` directory are deleted. Only the domains that actually read a secret need `secretsmanager:GetSecretValue`. The import time `load_app_secrets()` in `config.py` is gone as of the lazy secret resolution PR, so a read only domain such as `vehicles` makes no Secrets Manager call and drops the grant. `log_retention_days` 14 becomes 7 |
| `apigateway.tf` | 33 | `route_keys = ["$default"]` becomes an explicit path-prefix route map, one route per domain, each bound to its own integration. Per-route throttling is set here as layer 1 of the rate limiting standard. `access_log_retention_days` 14 becomes 7. Keep `$default` pointing at the monolith throughout the strangler migration |
| New `ecr.tf` | n/a | One repository per domain per environment, each with a lifecycle rule, plus the base image repository. Nine domain repositories plus the base, per environment. Needs a new platform module |
| `s3.tf` | 65 | `module "lambda_artifacts"` and the `carmodpicker-<env>-lambda-artifacts` bucket are removed once zips are gone. Keep until the last domain is cut over |
| `iam_github_actions.tf` | 65 | The deploy role loses `s3:PutObject` on the artifacts bucket and gains ECR push, `ecr:GetAuthorizationToken`, `BatchCheckLayerAvailability`, `PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`. `lambda:UpdateFunctionCode` widens from one function ARN to nine |
| `monitoring.tf` | 20 | `module "alarms"` is per-function today. Nine functions must not become nine times the alarms; the aggregate approach already used for DynamoDB should extend to Lambda errors and throttles |
| `outputs.tf` | 94 | `lambda_function_name` and `lambda_function_arn` become maps. `LAMBDA_FUNCTION_NAME` and `LAMBDA_ARTIFACTS_BUCKET` environment variables change shape |
| `variables.tf` | 133 | Add the domains map and the image tag input |
| `dynamodb.tf` | 15 | Gains the `<prefix>-rate-limits` table with its TTL attribute for the shared limiter. The existing 25 tables and `dynamodb_tables.json` are otherwise unchanged |
| `ses.tf`, `route53.tf`, `acm.tf`, `cloudfront.tf`, `cloudfront_function.tf`, `staging_access_gate.tf`, `management.tf`, `secretsmanager.tf`, `providers.tf`, `locals.tf`, `versions.tf`, `data.tf` | n/a | Unchanged |

### Platform module changes

The registry is at v1.7.1 and all twelve modules are already consumed by this
application. Three changes are needed.

**`lambda-function` already supports OCI images.** When this inventory was first
written the module was Zip-only: `package_type` appeared nowhere, `runtime` and
`handler` were both required with non-empty validations, `image_config` was not
exposed, and `image_uri` was absent from `ignore_changes`. All four were fixed
while Portfolio was split. The module now sets `package_type` from the shape of
the `code` object, accepts `runtime = null` and `handler = null` on an image
function, exposes `image_config`, and carries `image_uri` on `ignore_changes` so
a CI `UpdateFunctionCode` survives the next plan. Nothing further is needed here.

**`http-api` already supports a route-to-integration map.** The module took an
`integrations` map and a `routes` map keyed by route key during the Portfolio
split, alongside `default_integration`. CarModPicker already consumes the fixed
major version, `~> 2.0`, and already passes a single integration under the key
`legacy` with `default_integration = "legacy"` and `routes = {}`. Adding a
domain is adding one entry to each map; the `legacy` key must be preserved
verbatim because the module's `moved` blocks target it.

**An `ecr-repository` module exists.** It creates one repository per call with a
lifecycle policy input, image tag mutability, scan on push, and a repository
policy allowing named accounts to pull. It is invoked from a `for_each` in the
application, once per domain per environment.

Also worth doing while the modules are open: `lambda-function` and `http-api`
both validate `log_retention_days` and `access_log_retention_days` against the
accepted CloudWatch list, so moving to 7 days is an input change in the
application repository, not a module change. There is no standalone log-group
module and none is needed.

### How the six workflows collapse

Today there are six workflows, three CI and three deploy, each with its own
`paths:` filter. Under `workflow_call` consumers in an organisation `.github`
repository:

| Today | Becomes |
|---|---|
| `backend-ci.yml` (76 lines) | Calls `webbpulse/.github/.github/workflows/python-ci.yml`. The steps are already generic: black, isort, pyright, bandit, pip-audit, pytest with coverage |
| `frontend-ci.yml` (61) | Calls `node-ci.yml`. prettier, eslint, type-check, npm audit, vitest, madge, build |
| `chrome-extension-ci.yml` (48) | Calls the same `node-ci.yml` with different inputs |
| `backend-deploy.yml` (131) | Calls `container-deploy.yml`, once per domain via a matrix. The zip build steps are deleted outright |
| `frontend-deploy.yml` (109) | Calls `spa-deploy.yml`. Unchanged in substance: build, sync to S3, invalidate CloudFront |
| `chrome-extension-deploy.yml` (177) | Stays a bespoke workflow. It publishes to the Chrome Web Store, self-commits a version bump to `main`, and touches no AWS |

That is five reusable workflows plus one bespoke one, with the per-application
files reduced to a `uses:` line and an inputs block. The three CI workflows
already run on pull requests into both `main` and `staging`, so the gap noted in
CLAUDE.md is closed.

### The deploy race guard with N functions

`backend-deploy.yml` and `frontend-deploy.yml` both carry a byte-identical step
named "Wait for Terraform run to complete", placed after the AWS OIDC step and
before any mutating AWS call. It polls
`GET /api/v2/workspaces/$TFC_WORKSPACE_ID/runs?page[size]=1`, parses the newest
run's status, and breaks on `applied`, `planned_and_finished`, `discarded`,
`errored`, `canceled`, `force_canceled`, or `no_runs`. It tries 40 times with a
15 second sleep, so 10 minutes, then hard-fails the deploy.

Moving to nine functions changes this in three ways.

First, the poll must run **once per deploy, not once per function**. Nine matrix
jobs each polling the same workspace would be nine times the API calls, and worse,
they could each observe a different terminal state as runs queue behind one
another. The poll belongs in a single gate job that the nine image-push jobs
depend on.

Second, the window between the gate passing and the last function being updated
grows with the number of functions. Today the guard protects one
`update-function-code` call. With nine, an apply that starts midway through the
matrix can race the tail of it. The mitigation is to build and push all nine
images first, then take the gate, then run the nine `update-function-code` calls
as fast as possible, so the exposed window holds only the update calls rather
than nine image builds.

Third, two existing weaknesses get worse at nine times the volume and should be
fixed in the reusable workflow rather than carried over. `curl -sfg` means an
HTTP error, a bad token or a wrong workspace id, exits non-zero and aborts the
step instead of retrying. And the poll inspects only the single newest run, so a
run queued behind it is never observed.

`backend-deploy.yml` already sets `concurrency: backend-deploy-<ref>` with
`cancel-in-progress: false`, which should be kept. `frontend-deploy.yml` has no
concurrency group and should gain one.

### Docs-only changes do not deploy

Confirmed by reading the `paths:` block of all six workflows. Every one has a
filter, and the only prefixes any of them match are `backend/`, `frontend/`,
`chrome-extension/`, and each workflow's own file. None has `paths-ignore`, none
has a bare `**`, and none mentions `docs/`. A change touching only `docs/**`
therefore triggers no workflow at all. `terraform/**` likewise triggers nothing,
because infrastructure is applied through HCP Terraform's own VCS integration
rather than GitHub Actions.

---

## 6. Risks and open questions

- Resolved. The platform `lambda-function` module gained real image support, and `http-api` gained a route-to-integration map, both during the Portfolio split. Neither is a blocker any more.
- Nine cold starts replace one, and the current 29 second integration timeout leaves no headroom if an image is large; the shared base image is the mitigation but needs measuring.
- The user delete in `users.py` cascades writes into five other domains' tables. Section 2.1 settles the mechanism, a tombstone plus stream fan-out to per-domain cleanup handlers, but the eventual consistency it introduces means every read path must tolerate a half-cleaned entity.
- `part_service.purge_related_rows_for_parts` writes to three other domains' tables and goes async by the same mechanism as the user cascade.
- `vote_service` denormalises `net_votes` onto `parts` only, not onto `build_lists` as an earlier draft stated. It becomes a stream-driven handler owned by `catalog`, so `moderation` ends up with no cross-domain write at all.
- Cross-domain table reads are proposed as allowed with read-only IAM; if the owner wants strict per-domain data ownership instead, several read paths become service calls and latency rises.
- The `vehicles` domain merging car generations with search is the weakest boundary and may be better split or folded into `catalog`.
- PyJWT here versus python-jose in Portfolio must be settled before the shared auth module is cut.
- Eager OpenTelemetry SDK init would add cold-start cost on all nine functions; the lazy initialisation proposed in section 3 needs measuring against the 29 second integration timeout before the first cutover.
- Whether the browser keeps Sentry or moves to OpenTelemetry is not settled by the backend observability decision and needs its own call.
- The CloudWatch metric filter for errors must be tuned so nine functions do not produce nine times the alarm noise through the shared `api-alarms` SNS topic.
- The rate limiter is in-memory and is not enforced across Lambda execution environments, and it keys on the caller-supplied leftmost `X-Forwarded-For` hop, so the configured limits are both diluted and trivially bypassable in production today. The layered standard in section 1 replaces it.
- Tailwind v4 here versus v3 in Portfolio blocks sharing any component that emits classes, including the whole UI kit.
- Portfolio's frontend has one test file against about 90 here, so extracting shared frontend code has no regression net on the Portfolio side.
- Nine functions could multiply the CloudWatch alarm count; the aggregate pattern already used for DynamoDB should be extended rather than repeated per function.
- Nine images per deploy multiplies ECR storage and pull time, so the lifecycle rule needs to be aggressive from day one.
- The strangler cutover means the monolith and the extracted domains run the same code from two roots simultaneously, so any drift between the roots is a production risk until the last domain moves.
- CodeArtifact adds a hard dependency on the new Platform account being reachable during every build, including the base image build. That account is being vended now, so the shared-package PRs are blocked on it existing and on cross-account CodeArtifact read being wired to the member accounts.
- Moving retention from 14 days to 7 shortens the debugging window on exactly the deploys most likely to need it.
- The `init_cars` and `init_categories` startup tasks run from the `main.py` lifespan. Left as they are, all nine functions would race the same seed writes on every cold start. They need a single owner, a one-off job or a gate to one function, before the first cutover.
- The rate limit table is one more DynamoDB write on every auth and mutating request. It fails open by design, but the added latency and cost on the hot write paths should be measured before the limiter is switched on in production.
- The `ingestion` domain is thinner than its name suggests, since `crawled_pages` touches no repository and the listing writes belong to `catalog` and `build-lists`. It may be better named `admin` or dissolved into `catalog`.
- The frontend `services/Api.ts` shim is still imported by 53 non-test source modules, not the three named in an earlier draft. Removing it is a mechanical rewrite of every import site across pages, components, hooks and contexts, so it is its own PR and a real one, not a cleanup folded into the HTTP package extraction.

## 7. Suggested PR sequence

Sizes are rough: small is under 200 lines changed, medium 200 to 800, large above
800.

| # | PR | Size | Notes |
|---|---|---|---|
| 1 | This inventory document | small | Docs only, triggers nothing |
| 2 | Platform modules: `lambda-function` gains real image support | medium | `package_type`, optional `runtime`/`handler`, `image_config`, `image_uri` in `ignore_changes`. Tag v1.8.0 |
| 3 | Platform modules: `http-api` gains a route-to-integration map | medium | Backward compatible, existing single-integration callers keep working |
| 4 | Platform modules: new `ecr` module | small | One repository per call, lifecycle rule, scan on push, pull policy scoped to the one account that runs the images |
| 5 | Terraform: ECR repositories and the base image, no functions yet | small | Nine domain repositories plus the base, per environment. Additive only, nothing cuts over |
| 6 | Backend: `src/` layout and the monolith composition root, no domain split | large | Pure move plus import rewrite. The existing 97 test files must pass untouched. This is the riskiest mechanical change and deserves its own PR |
| 7 | Backend: the route inventory contract test | small | Locks the 176 routes and their paths before anything moves. Must enumerate `app.routes`, since 9 routes are generated at runtime and invisible to a decorator grep. Merge before PR 8 |
| 8 | Rate limiting layer 2: the `<prefix>-rate-limits` table and the shared fixed-window limiter | small | Replaces the in-memory limiter and the `X-Forwarded-For` key with the API Gateway request context. Independent bug fix, can land any time, and should land early because the current limiter is bypassable |
| 9 | Backend: carve out `media` as the first domain package, both roots | medium | Smallest domain at 8 routes, and the only one holding bucket-wide S3 grants, so it proves the IAM split |
| 10 | Dockerfile, base image, and the container build workflow | medium | Builds and pushes but does not yet route traffic |
| 11 | Terraform: the `media` function plus one path-prefix route, `$default` still the monolith | medium | The first real strangler cut. Per-route throttling goes in here as layer 1. Verify, then leave it running for a while |
| 12 | Reusable workflows in the org `.github` repository | medium | `python-ci`, `node-ci`, `container-deploy`, `spa-deploy`, and the fixed single-gate Terraform poll |
| 13 | CarModPicker workflows become `workflow_call` consumers | small | Six files shrink to `uses:` blocks |
| 14 | Startup tasks get a single owner | small | `init_cars` and `init_categories` move out of the lifespan so nine functions do not race the same seed writes |
| 15 to 19 | One PR per domain: `build-logs`, `moderation`, `vehicles`, `ingestion`, `build-lists` | medium each | Ordered smallest first. Each is a package carve-out plus its Terraform function and route |
| 20 | Cross-domain event plumbing: tombstones, the stream or queue, and the per-domain cleanup handlers | large | Section 2.1. Must land before `catalog` and `users`, since both depend on it to stop writing into other domains' tables. Includes the tombstone-aware read paths |
| 21 | `identity` domain | medium | Carve-out plus function and route |
| 22 | `catalog` domain, including the part purge going async and the `net_votes` handler | large | Depends on PR 20. The `net_votes` write moves here from `moderation`, which then drops its last cross-domain write |
| 23 | `users` domain, including the delete cascade going async | large | Deliberately last, it is the hardest coupling. Depends on PR 20 |
| 24 | Retire the `$default` monolith route, the artifacts bucket, and the zip path | small | Only after every domain has run in production |
| 25 | Log retention to 7 days everywhere | small | Single input change once the function set is stable |
| 26 | `webbpulse` tier 1: secrets, Dynamo client, serialization, settings base, CORS, health and ready | medium | The near-identical, framework-neutral set. No conflicts to settle first. Blocked on the Platform account and CodeArtifact existing |
| 27 | `webbpulse` OpenTelemetry module with lazy Lambda init | medium | Neutral core plus FastAPI and Lambda adapters. Land before the domain carve-outs so each domain adopts it on the way through |
| 28 | Terraform: X-Ray, the error metric filter, and `api-alarms` wiring | small | Completes the observability path before the first domain relies on it. The Lambda role already carries the X-Ray write permissions |
| 29 | `webbpulse` tier 2: repository, table specs, CRUD router | large | Requires the PyJWT decision and Portfolio's data-model migration to be scoped first |
| 30 | CarModPicker consumes `webbpulse` | medium | Deletes the duplicated modules here |
| 31 | Portfolio consumes `webbpulse` | medium | Proves the package is genuinely shared, not just extracted |
| 32 | Frontend: delete the `services/Api.ts` shim | medium | Rewrites 53 import sites onto `src/api/*`. Prerequisite for any HTTP package extraction |
| 33 | `@webbpulse/tsconfig`, `eslint-config`, `prettier-config` | small | The real near-term frontend win, no runtime risk |
| 34 | `@webbpulse/ui` and `@webbpulse/react` | large | Blocked on aligning Tailwind versions with Portfolio |

PRs 2 through 5, 8, 12, and 33 are independent of the backend restructure and can
run in parallel with PR 6. PR 27 should land before the domain carve-outs so that
each domain picks up OpenTelemetry as it moves rather than being retrofitted
afterwards. PR 20 is the new hard gate: `catalog` and `users` cannot be carved
out before it, which is why the domain order puts the five self-contained domains
first and the three coupled ones after. Everything from PR 9 onward is otherwise
sequential by design, since each strangler cut should be observed in production
before the next one starts.

The shared-package PRs, 26 onwards, additionally depend on the new Platform
account being vended and cross-account CodeArtifact read reaching the member
accounts. They are sequenced late for that reason as much as for their own
difficulty.