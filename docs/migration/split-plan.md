# CarModPicker per-domain split plan

Status: plan. No application code, Terraform, or workflows change in the branch
that carries this document. It is the executable companion to
`docs/migration/inventory.md`, and it assumes that document's nine-domain map.

The equivalent work has already been done in WebbPulse-Portfolio. Where Portfolio
settled a question, this plan takes the settled answer rather than re-deriving it,
and where CarModPicker differs the difference is called out explicitly. The
mistakes Portfolio made on the way are recorded in that repository's
`docs/migration/container-image-workflow-gaps.md`; section 4 here carries the
fixes forward so they are not repeated.

## 0. What changed since the inventory was written

The inventory's own amendments section lists the six corrections. Three of them
change what this plan has to build, so they are restated here in terms of work.

**No platform module work is on the critical path.** `lambda-function` deploys
OCI images, `http-api` takes a route-to-integration map, and `ecr-repository`
exists. The inventory's PR sequence put three module PRs ahead of everything
else; they are gone. The first Terraform PR here is ECR repositories in the
application, not a module change.

**The base image is fixed and pinned by digest.**
`432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7`.
It already carries the AWS Lambda Web Adapter at `/opt/extensions/lambda-adapter`
and a Python runtime. CarModPicker's deploy role already has pull access to it
and `sts:GetServiceBearerToken` for CodeArtifact, both added in #316. What the
role still lacks is push access to CarModPicker's own ECR repositories.

**The alarm module has a ceiling that this application hits exactly.**
`api-alarms` v2.1.0 aggregates Lambda alarms through `lambda_function_names`,
capped at ten functions because the aggregate is CloudWatch metric math over
positionally-named metrics. Nine domains plus the monolith is ten. Section 3.6
is about what happens on the tenth cut.

One thing that is genuinely different here and has no Portfolio precedent:
**CarModPicker's API prefix is `/api`, not `/api/v1`.** Every route key in
section 3.5 differs from Portfolio's by that segment.

---

## 1. Domain map

Nine domains, as locked. The code does argue for a different count in one place,
and section 1.5 says where and why the answer is still nine.

### 1.1 Routes per domain

Counts are from importing `app.main:app` and walking `app.routes`, not from
grepping decorators. Nine routes across three modules are generated at runtime by
`BaseDynamoEndpointRouter` and are invisible to a grep, which is why the
decorator count is 162 and the real count is 171.

| Domain | Endpoint modules | Routes | Path prefixes served |
|---|---|---|---|
| `identity` | `auth/core`, `auth/oauth`, `auth/two_factor`, `auth/webauthn` | 24 | `/api/auth` |
| `users` | `users`, `app_settings` | 14 | `/api/users`, `/api/app-settings` |
| `catalog` | `parts`, `part_manufacturers`, `categories`, `retailers` | 43 | `/api/parts`, `/api/part-manufacturers`, `/api/categories`, `/api/retailers` |
| `vehicles` | `car_generations`, `search` | 11 | `/api/car-generations`, `/api/search` |
| `build-lists` | `build_lists`, `build_list_parts`, `build_list_phases`, `build_list_labor_estimates` | 34 | `/api/build-lists`, `/api/build-list-parts`, `/api/build-list-phases`, `/api/build-list-labor-estimates` |
| `build-logs` | `build_logs` | 5 | `/api/build-logs` |
| `moderation` | `votes`, `reports`, `bug_reports` | 20 | `/api/votes`, `/api/reports`, `/api/bug-reports` |
| `media` | `images` | 8 | `/api/images` |
| `ingestion` | `crawled_pages`, `part_price_alerts`, `admin/db_ops`, `admin/stats` | 12 | `/api/crawled-pages`, `/api/part-price-alerts`, `/api/admin/db-ops`, `/api/admin/stats` |

171 routes under `/api`, plus the five root routes in `main.py` (`/`, `/health`,
`/ready`, `/sitemap.xml`, `/sitemap-{name}.xml`) that every function serves
locally, for 176. FastAPI's `/docs`, `/docs/oauth2-redirect`, `/redoc`, and
`/api/openapi.json` are excluded from every count.

Auth split across the 176: 66 require a user, 31 require an admin, 13 take an
optional user, 66 are fully public.

Two routes are unauthenticated writes and both belong to `catalog`:
`POST /api/parts/{part_id}/listings` and `POST /api/parts/price-history`. They
take a logger and a repository bundle and no user dependency at all, unlike every
other mutating route in the application. Carving `catalog` out puts both behind
their own function with their own IAM, which makes the exposure easier to see and
easier to fix, but the split does not fix it. It should be settled on its own
before `catalog` moves, not as part of the move.

### 1.2 Table ownership

Twenty-five tables, one owner each. The owner is the only writer once the split
is complete. "Written today by" records what the code actually does now, which is
what section 1.3 has to unwind.

| Table | Owner | Also written today by |
|---|---|---|
| `users` | `users` | `identity` (oauth link, webauthn registration, password and 2FA changes) |
| `oauth_accounts` | `identity` | `users` (delete cascade) |
| `webauthn_credentials` | `identity` | `users` (delete cascade) |
| `app_settings` | `users` | none |
| `parts` | `catalog` | `moderation` (`net_votes` denormalisation), `users` (delete cascade), `ingestion` (`admin/db_ops`) |
| `part_cars` | `catalog` | `users` (delete cascade), `ingestion` |
| `part_listings` | `catalog` | `build-lists` (price capture), `users` (delete cascade) |
| `part_price_history` | `catalog` | `build-lists` (price capture), `users` (delete cascade) |
| `part_manufacturers` | `catalog` | `ingestion` |
| `categories` | `catalog` | `ingestion` |
| `retailers` | `catalog` | none |
| `car_makes` | `vehicles` | `ingestion` (seed and delete-all) |
| `car_models` | `vehicles` | `ingestion` |
| `car_generations` | `vehicles` | `ingestion` |
| `build_lists` | `build-lists` | `users` (delete cascade), `ingestion` |
| `build_list_parts` | `build-lists` | `catalog` (part purge), `users` (delete cascade) |
| `build_list_phases` | `build-lists` | `users` (delete cascade) |
| `build_list_labor_estimates` | `build-lists` | `users` (delete cascade) |
| `build_logs` | `build-logs` | `build-lists` (created with the list), `users` (delete cascade) |
| `build_log_posts` | `build-logs` | `users` (delete cascade) |
| `votes` | `moderation` | `catalog` (part purge), `users` (delete cascade), `ingestion` |
| `reports` | `moderation` | `catalog` (part purge), `users` (delete cascade) |
| `bug_reports` | `moderation` | none |
| `part_price_alerts` | `ingestion` | `catalog` (part purge), `users` (delete cascade) |
| `image_source_mappings` | `media` | none |

Cross-domain **reads** are allowed with read-only IAM. Cross-domain **writes**
are not, and every one in the table above has to go somewhere. That is section
1.3.

### 1.3 Cross-domain calls and what becomes async

Five seams. They are listed hardest first, because the order the domains are cut
in is derived from this list rather than from route counts.

**Seam 1: the user delete cascade.** `users.py` deletes a user and then writes
into roughly fifteen tables across five other domains: `oauth_accounts`,
`webauthn_credentials`, `build_lists`, `build_list_parts`, `build_list_phases`,
`build_list_labor_estimates`, `build_logs`, `build_log_posts`, `parts`,
`part_cars`, `part_listings`, `part_price_history`, `part_price_alerts`, `votes`,
`reports`. This is the single largest coupling in the application and it is why
`users` is cut last.

It becomes a tombstone. `users` writes `deleted_at` and `deleted` onto the user
item and returns. A DynamoDB stream on `users` feeds an SQS queue per subscribing
domain, and each domain drains its own queue and deletes its own rows with its
own IAM. The tombstone is the contract: `users` owns it, and every domain that
reads a user must treat a tombstoned user as absent.

The consequence is what makes this hard rather than tedious. Between the
tombstone write and the last queue draining, the application is in a half-deleted
state, and every read path that joins to a user has to tolerate it. Concretely,
`build-lists`, `build-logs`, `moderation`, and `vehicles` all read `users` to
attach an author, and all four must filter tombstoned users out rather than
rendering a blank author. That filtering has to land **before** `users` is cut,
not with it.

**Seam 2: the part purge.** `part_service.purge_related_rows_for_parts` deletes a
part and then writes into `build_list_parts`, `votes`, `reports`, and
`part_price_alerts`, owned by `build-lists`, `moderation` twice, and `ingestion`.
Same mechanism, smaller blast radius: a tombstone on `parts` plus a stream, with
`build-lists`, `moderation`, and `ingestion` each draining their own queue.

The read-path consequence is real here too and is more visible to users than the
user cascade. A build list that contains a purged part must not render a hole; it
must drop the row. So `build-lists` gains a tombstone check on the part join
before `catalog` is cut.

**Seam 3: the vote denormalisation.** `vote_service._sync_part_net_votes` writes
`parts.net_votes` after every vote create, update, and remove. `moderation` owns
`votes`; `catalog` owns `parts`. This is the only cross-domain write that is not
a delete.

It inverts rather than going through a tombstone. A stream on `votes` feeds a
handler owned by `catalog`, which recomputes and writes `net_votes` on the part
it owns. `moderation` stops writing to `parts` entirely and is left with no
cross-domain write at all, which is why `moderation` can be cut early despite
being a 20-route domain.

Worth being precise about what this changes: `net_votes` becomes eventually
consistent. A user who votes and immediately reloads may see the old count. The
vote itself is synchronous and immediately visible; only the denormalised
aggregate lags. Whether that is acceptable is a product call, and it is in the
open questions. The alternative is for the vote route to return the computed
count and for the client to use the response rather than re-reading, which is a
frontend change of about one line per call site and avoids the problem entirely.

**Seam 4: the price alert email.** `part_listing_service` calls
`evaluate_alerts_for_listing` inline on the request thread. That function reads
`part_price_alerts`, `parts`, `retailers`, and `users`, and then sends SES mail,
all before the listing write returns. `catalog` owns the listing;
`part_price_alerts` belongs to `ingestion`.

This one is the easiest to fix and the most worth fixing on its own merits, split
or no split. Today a price write blocks on a fan-out read plus an SES call inside
a 29 second Lambda, and there is no scheduler behind it: alerts fire only when
some request happens to write a price. It becomes a stream on `part_listings`
feeding an `ingestion` handler that owns both the alert rows and the SES send.
`catalog` loses its SES grant entirely.

**Seam 5: the read fan-outs.** Two of them. `search.py` is one route reading
`car_generations`, `build_lists`, `users`, and `parts`, spanning four domains.
`bucket_orphan_utils.get_all_referenced_file_keys()` full-scans `parts`, `users`,
`car_generations`, `build_lists`, and `image_source_mappings` to find orphaned S3
objects.

Neither becomes async. Both are reads, and cross-domain reads are allowed with
read-only IAM. Search stays in `vehicles` with read grants on the four tables.
The orphan sweep stays in `media` with read grants on five. The reason to leave
them is that turning either into service calls converts one Dynamo round trip
into three or four HTTP hops on a path that is already slow, and neither is on a
hot path: search is user-initiated and the orphan sweep is admin-initiated.

The orphan sweep deserves a flag anyway. It is five full table scans behind an
admin HTTP route in a 29 second Lambda, and it will time out as the tables grow.
It should become a scheduled job rather than a route, but that is its own change
and not a prerequisite for the split.

### 1.4 Route ordering

API Gateway HTTP API resolves in a fixed precedence: an exact literal match
first, then a `{proxy+}` greedy match, then `$default` last. That ordering is
what makes the strangler safe. A domain's explicit prefix route always wins over
`$default`, so adding a route moves exactly that prefix and nothing else, and
removing it moves the prefix back.

Inside a domain, FastAPI resolves in registration order, and CarModPicker has
several places where that is load-bearing today. They survive the split unchanged
because a domain's modules keep their relative registration order, but each is a
trap if a module is ever moved between domains.

| Hazard | Where | Why it currently resolves |
|---|---|---|
| `/api/parts/price-history` vs `/api/parts/{part_id}/price-history` | `catalog` | Different segment count and method |
| `/api/parts/count`, `/filter-options`, `/check-url`, `/with-votes` vs `/{entity_id}` | `catalog` | Literals are registered before the generated `{entity_id}` route |
| `/api/part-manufacturers/counts/by-source` vs `/{id}/parts` | `catalog` | Distinct two-segment shape |
| `/api/part-price-alerts/unsubscribe` vs `/{alert_id}` | `ingestion` | Survives only because `/{alert_id}` is PATCH and DELETE and there is no GET detail route. Fragile: adding `GET /{alert_id}` breaks unsubscribe silently |
| `/api/build-list-parts/parts/{part_id}/build-lists/count` vs `/{build_list_id}` | `build-lists` | Three-segment shape differs. A bare `/api/build-list-parts/parts` would match `{build_list_id}` |
| `/api/users/admin/users` vs `/{user_id}` | `users` | Two segments. A bare `/api/users/admin` would match `{user_id}` |
| `/api/build-lists/with-votes`, `/count`, `/car/{id}`, `/user/me` vs generated `{entity_id}` | `build-lists` | Literals registered first |

The `part-price-alerts` row is the one to fix rather than document. It is one
route away from a silent production break, and the fix is to register
`/unsubscribe` before the parameterised routes. That is a two-line change and
should go in early, independent of the split.

There is one genuine cross-domain ordering conflict and it is in the API Gateway
map rather than in FastAPI. `ingestion` serves `/api/admin/db-ops` and
`/api/admin/stats`, two children of `/api/admin`. There is no route at
`/api/admin` itself, so two explicit prefix routes are needed rather than one,
and no other domain may ever claim `/api/admin/{something}` without taking it
into account.

### 1.5 Where the code argues for a different count

Nine is the locked default and this plan proposes nine. Two boundaries are weak
enough to be worth stating.

`vehicles` merges `car_generations` with `search`, and the only thing they share
is that `search.py` imports `car_generation_service`. Search reads four domains'
tables; car generations reads three. It is a merge of convenience, made because
`vehicles` would otherwise be the smallest domain at eight routes, and it is the
one place where the domain name does not describe the contents. The alternatives
are folding `car_generations` into `catalog`, which makes `catalog` a 54-route
domain and worsens the largest boundary to fix the smallest, or giving search its
own function, which makes ten domains and pushes the alarm ceiling from tight to
breached. Nine, with search in `vehicles`, is the least bad of the three.

`ingestion` is thinner than its name. `crawled_pages` is one route that touches
no repository at all; it parses HTML the Chrome extension posts and returns the
result. The listing writes that the name implies belong to `catalog`. What is
actually in `ingestion` is the price alerts and the two admin modules, which is a
coherent function but is closer to `admin` than to `ingestion`. Renaming it is
cosmetic and cheap before the first cut and expensive after, since the name is in
the ECR repository, the function name, the image tag, and the log group. It is in
the open questions for that reason.

The count the code would argue for, left to itself, is seven: fold `search` into
`catalog`, fold `build-logs` into `build-lists`, and fold `ingestion`'s admin
modules into the domains they administer. That is rejected because it makes
`catalog` enormous and puts admin writes to six domains' tables behind six
different functions, which is worse than one broad admin function. Nine stands.

---

## 2. Code layout

### 2.1 Two composition roots

Root A, `app/composition/app.py`, mounts every domain into one FastAPI
application. It serves local development, the entire existing test suite, and any
future container. Root B, `app/entrypoints/<domain>.py`, is one file per domain
and is what a deployed function runs.

Root A composes with `include_router`, never with `mount`. This is the single
most important detail in the layout and Portfolio learned it the hard way:
Starlette strips a mount path before the sub-application sees it, and a mounted
sub-application contributes nothing to the parent's OpenAPI document. Mounting
would give a local application whose routes resolve but whose `/api/openapi.json`
is empty, and whose route paths differ from production by the mount prefix. Both
roots must produce byte-identical paths, because the contract test in section 8
compares them.

### 2.2 Package structure

```
backend/app/
  composition/
    app.py          Root A, all domains
    wiring.py       Domain dataclass and build_domain_app
    settings.py     lazily resolved settings
  entrypoints/
    identity.py     Root B, one per domain
    users.py
    catalog.py
    vehicles.py
    build_lists.py
    build_logs.py
    moderation.py
    media.py
    ingestion.py
  domains/
    identity/
      routers/      the four auth modules
      services/
      repositories/
      schemas/
    users/
    ...
  shared/           what stays common until it moves to the webbpulse package
```

The `Domain` descriptor mirrors Portfolio's, with the service name template
changed:

```python
@dataclass(frozen=True)
class Domain:
    name: str
    title: str
    load_routers: Callable[[], "list[APIRouter]"]
    router_prefix: str = API_PREFIX          # "/api" here, not "/api/v1"
    router_tags: tuple[str, ...] = ()
    requires_secrets: tuple[str, ...] = ()
    seeds: bool = False
    extra: dict = field(default_factory=dict)

SERVICE_NAME_TEMPLATE = "carmodpicker-{domain}"
```

`load_routers` is a callable rather than a list so that importing the descriptor
does not import the routers. Root B imports one domain's descriptor and calls its
loader; the other eight domains' modules are never imported in that process. That
is the whole point of the indirection and it is what keeps cold start down.

### 2.3 The blocker in the current code

`app/api/dependencies/repositories.py` defines a frozen dataclass `Repositories`
that instantiates all twenty-five repositories at module import, and
`get_repositories()` returns it. Every route in the application depends on it.
Left as it is, every one of the nine functions imports all twenty-five repository
modules, and through them the entire data layer, on every cold start.

This has to be unwound before any domain is carved out, and it is the reason the
source-layout PR is large and comes early. The replacement is a per-domain
repository bundle: each domain declares the repositories it needs, and
`get_repositories()` in that domain's process returns only those. The route
signatures do not change, so the change is mechanical, but it touches every
endpoint module.

`app/core/config.py` has a related problem. `load_app_secrets()` runs at import
time, so every function needs `secretsmanager:GetSecretValue` at cold start
whether or not it uses a secret. Portfolio solved this by making secrets optional
fields resolved lazily through a `_resolve_secret` helper, with a
`require_secrets()` call at the point of use rather than a validator that raises
at import. The same change applies here and it is what lets `vehicles`, which is
entirely read-only and needs no secret, drop the grant.

This is sharper than it sounds. Importing `app.core.config` today performs a
network call to Secrets Manager and re-raises on failure, which means the module
is un-importable without AWS credentials. Any tooling that imports the
application without credentials fails, and that includes the contract test in
section 2.7, which has to import all nine Root B applications. So the lazy
resolution is not an optimisation, it is a prerequisite for the test that makes
every cut verifiable.

### 2.4 Entrypoint shape

```python
# app/entrypoints/vehicles.py
from app.composition.wiring import build_domain_app
from app.domains.vehicles import DOMAIN

def build_app():
    return build_domain_app(DOMAIN)

def main():
    configure_logging(level=..., service=..., environment=...)
    configure_tracing(service=..., environment=...)
    run_uvicorn(build_app())

if __name__ == "__main__":
    main()
```

`build_app()` must be importable with no AWS credentials and no network, because
the contract test imports all nine of them. Everything that needs AWS goes in
`main()`.

### 2.5 One parameterised Dockerfile

One `backend/Dockerfile` for all nine domains, selected by `ARG DOMAIN`.

```dockerfile
ARG BASE_IMAGE=432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7

FROM ${BASE_IMAGE} AS builder
USER root
RUN --mount=type=secret,id=codeartifact_token,required=true \
    PIP_INDEX_URL="https://aws:$(cat /run/secrets/codeartifact_token)@webbpulse-432410731887.d.codeartifact.us-west-2.amazonaws.com/pypi/python/simple/" \
    pip install --no-cache-dir -r requirements-lambda.txt

FROM ${BASE_IMAGE}
ARG DOMAIN
RUN test -n "${DOMAIN}" || (echo "DOMAIN build arg is required" && exit 1)
ENV DOMAIN=${DOMAIN} \
    AWS_LWA_PORT=8080 \
    AWS_LWA_ASYNC_INIT=true \
    AWS_LWA_READINESS_CHECK_PATH=/health
CMD ["sh", "-c", "exec python -m app.entrypoints.${DOMAIN}"]
```

Four details are load-bearing and each of them cost Portfolio a debugging session.

The CodeArtifact token is a **BuildKit secret mount**, never a build argument and
never an `ENV`. A build argument persists in `docker history` on the pushed image
and is readable by anyone who can pull it. The builder stage runs as `USER root`
because BuildKit secrets are mounted root-owned with mode 0400 and a non-root
builder cannot read them. The `PIP_INDEX_URL` is assembled inside the `RUN` so
the token never becomes a layer.

`AWS_LWA_READINESS_CHECK_PATH=/health` requires `/health` to do no I/O.
CarModPicker's `/health` is a static dictionary and `/ready` is the one that calls
`check_db_ready()`, so `/health` is correct for all nine domains and no domain
needs the `tcp` protocol fallback. This is better than Portfolio, where one domain
had to fall back to `AWS_LWA_READINESS_CHECK_PROTOCOL=tcp`.

`AWS_LWA_ASYNC_INIT=true` lets initialisation continue past the ten second
init phase, which matters because the base image plus FastAPI plus the domain's
slice of the data layer is not fast to import.

There is no Lambda handler and no Mangum. `app/lambda_handler.py` is deleted with
the monolith at the end, not before.

### 2.6 Architecture change

The monolith is `x86_64`, pinned in three places: `architectures` in
`lambda.tf`, the two `--platform manylinux` flags in `backend-deploy.yml`, and
implicitly in `requirements-lambda.txt`'s native wheels. The domain functions
should be `arm64`, matching Portfolio and the shared base image's primary
architecture, which is cheaper per millisecond.

Three dependencies have native wheels and need checking on `arm64` before the
first cut: `Pillow==12.3.0`, `bcrypt==5.0.0`, and `webauthn==2.7.1`. All three
publish `aarch64` manylinux wheels, so this should be a non-event, but it is
verified by building the `media` image, which uses Pillow, as the first one.

`curl_cffi` is in `requirements.txt` but deliberately not in
`requirements-lambda.txt`, and it must stay out. It is the crawler tier's TLS
impersonation library, has no server-side caller, and is the largest native
dependency in the tree.

### 2.7 Local development and tests

The existing 97 backend test files run against Root A and must pass untouched
through the source-layout PR. That is the acceptance criterion for that PR: a
pure move plus import rewrite, with a green suite and no test edits.

`backend/docker-compose.yml` keeps working unchanged. It runs DynamoDB Local and
MinIO on the host; the application runs against them from Root A.

A new test asserts that all nine Root B applications import with no AWS
credentials present and that the union of their route paths equals Root A's route
paths exactly. This is the contract that lets a cut be verified.

---

## 3. Terraform changes, in order

Every step is additive until 3.5, and 3.5 is reversible one route at a time.

### 3.1 ECR repositories

`terraform/ecr.tf`, new. A `for_each` over the nine domains calling
`ecr-repository`, one repository per domain per environment, in the service
accounts: staging `748861776298`, production `734702670403`. Repository names
`carmodpicker/<domain>`.

Image tag mutability **IMMUTABLE**, tags of the form `sha-<40 hex>`. Scan on
push enabled. A lifecycle rule expiring untagged images at one day and keeping
the last thirty tagged images, which at nine repositories per environment is the
difference between a bounded and an unbounded storage bill.

Immutability has a consequence for CI that section 4 handles: a rebuild of the
same commit fails the push rather than overwriting, so the build job needs an
existing-tag guard.

### 3.2 Deploy role

`iam_github_actions.tf`. The role already has CodeArtifact read,
`sts:GetServiceBearerToken`, and pull on the shared base image, all from #316.
It needs, added:

- `ecr:PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`,
  `BatchCheckLayerAvailability` on the nine CarModPicker repositories.
- `ecr:BatchGetImage` on the same nine, for the existing-tag guard.
- `lambda:UpdateFunctionCode`, `PublishVersion`, `GetFunction`,
  `GetFunctionConfiguration` widened from the single `module.lambda_api.function_arn`
  to the nine domain function ARNs plus the monolith.
- `lambda:InvokeFunction` on the nine, for the smoke test in section 4. Portfolio
  missed this and the smoke step failed on the first cut.

It keeps `s3:PutObject` on the artifacts bucket until the monolith is retired.

### 3.3 Lambda functions and the bootstrap order

`terraform/lambda_domains.tf`, new, replacing nothing yet. A `local.lambda_domains`
map carries per-domain memory, the secrets it needs, its write tables, and its
read tables. A `for_each` over it calls `lambda-function` with
`package_type = "Image"`, `runtime = null`, `handler = null`,
`architectures = ["arm64"]`, `log_retention_days = 7`, and
`attach_xray_write_policy = true`.

There is a chicken-and-egg problem here and it has a specific answer. A function
cannot be created without an image, and the image cannot be built by the deploy
workflow before the repository exists. So `variable "bootstrap_image_tag"`,
validated against `^sha-[0-9a-f]{40}$`, is set once to a tag that has been pushed
by hand or by a manual workflow run, the functions are created from it, and
thereafter CI's `UpdateFunctionCode` owns the image. `image_uri` is on the
module's `ignore_changes` list, which is what stops the next plan from reverting
CI's deploy back to the bootstrap tag.

Memory sizes start at the monolith's 1024 MB for `catalog` and `build-lists` and
512 MB for the rest, and are tuned after the first week of production data rather
than guessed now. Timeout stays 29 seconds to match the API Gateway integration
timeout; a longer function timeout is invisible because the gateway gives up
first.

### 3.4 Per-domain IAM

One `aws_iam_role_policy` per domain, built by `concat` of four statement groups:
logs on that domain's log group, DynamoDB write actions on its owned tables and
their indexes, DynamoDB read actions on the tables it reads, and
`secretsmanager:GetSecretValue` on the app secret for the domains that need it.

This replaces the monolith's four inline policies, which today grant
`table/carmodpicker-<env>-*` and its indexes to everything. The write action set
is the twelve Dynamo write actions; the read set is five.

Three domains have grants beyond Dynamo. `identity` and `ingestion` get
`ses:SendEmail` on the identity and the `carmodpicker-transactional` configuration
set; `catalog` loses SES when seam 4 moves. `media` gets `s3:PutObject`,
`GetObject`, `DeleteObject`, `HeadObject`, `ListBucket` on the user images
bucket, and `users` gets the first three of those for avatars. `vehicles` gets
Dynamo read and nothing else, not even Secrets Manager, once section 2.3's lazy
secret resolution lands. That makes `vehicles` the cheapest proof that the IAM
split is real.

### 3.5 API Gateway routes, one prefix at a time

`apigateway.tf`. The `integrations` map gains one entry per domain as that domain
is cut. The `legacy` key and `default_integration = "legacy"` stay exactly as
they are throughout, both because `$default` must keep serving everything not yet
cut and because the module's `moved` blocks target that key by name.

Route keys, with the `/api` prefix that differs from Portfolio:

| Domain | Route keys |
|---|---|
| `media` | `ANY /api/images/{proxy+}`, `ANY /api/images` |
| `build-logs` | `ANY /api/build-logs/{proxy+}`, `ANY /api/build-logs` |
| `moderation` | `/api/votes`, `/api/reports`, `/api/bug-reports`, each with a `{proxy+}` pair |
| `vehicles` | `/api/car-generations`, `/api/search`, each with a pair |
| `ingestion` | `/api/crawled-pages`, `/api/part-price-alerts`, `/api/admin/db-ops`, `/api/admin/stats`, each with a pair |
| `build-lists` | `/api/build-lists`, `/api/build-list-parts`, `/api/build-list-phases`, `/api/build-list-labor-estimates`, each with a pair |
| `identity` | `/api/auth`, with a pair |
| `catalog` | `/api/parts`, `/api/part-manufacturers`, `/api/categories`, `/api/retailers`, each with a pair |
| `users` | `/api/users`, `/api/app-settings`, each with a pair |

Both the bare prefix and the `{proxy+}` are needed. The bare one catches
`/api/images`; the greedy one catches everything below it. Omitting the bare
route sends the collection endpoint to `$default` and the detail endpoint to the
new function, which is the worst possible failure mode because it half works.

Per-route throttling goes in here as layer 1 of the rate limiting standard,
replacing the single stage-level 25 rps and 50 burst with per-domain limits.

`disable_execute_api_endpoint` and the staging gate authorizer apply uniformly and
do not change.

### 3.6 Alarms, and the ceiling

`monitoring.tf`. `api-alarms` moves from `~> 1.7` to `~> 2.1`, and
`lambda_function_name` becomes `lambda_function_names`, a list. Aggregate on:
`lambda_aggregate_alarm = true`, `lambda_aggregate_threshold = 0`.
`dynamodb_aggregate_alarm = true` stays as it is. `error_log_groups` becomes a
merge of the monolith's log group and the nine domains'.

The list order matters and is not cosmetic. The module builds CloudWatch metric
math over positionally-named metric ids, `m0`, `m1`, and so on, so reordering the
list rewrites every expression and replaces the alarm. Fix the order once, in the
same order as `local.lambda_domains`, and add a comment saying so.

**The ceiling.** The module caps `lambda_function_names` at ten, because beyond
that the metric math expression exceeds what CloudWatch accepts. Nine domains
plus the monolith is exactly ten. The list is full from the moment the ninth
domain is cut until the monolith is retired, and there is no headroom for a tenth
domain, a canary function, or a stream handler.

Three ways out, and the recommendation is the third.

*Wait it out.* The ceiling binds only between cutting the ninth domain and
retiring the monolith, which the sequence in section 6 puts within one PR of each
other. Cheapest, but it means the last cut has no room for error, and any
additional function during that window has no aggregate alarm.

*Two aggregate alarms.* Call the module twice with a different `name_prefix`,
splitting the functions into two groups of five or six. Doubles the alarm count
from one to two, which is still far better than ten, and removes the ceiling for
a long time. The cost is that a group's alarm no longer means "something in the
backend is erroring", it means "something in group A is erroring", which is a
worse signal.

*Lean on the log-based alarm.* `error_log_groups` produces a metric filter per
log group feeding a single dimensionless alarm, and it has no ceiling because it
is a count of matching log lines rather than metric math over named functions.
It already exists and already covers every function. The recommendation is to
keep `lambda_function_names` at its ten and treat it as the fast signal for
Lambda-level failures such as throttles and init errors, and to treat the
log-based `application-errors` alarm as the one that scales, adding every new
function's log group to `error_log_groups` without touching the capped list. If a
tenth domain ever appears, it goes into `error_log_groups` only, and the capped
list keeps the nine plus the monolith until the monolith is retired and a slot
frees up.

This should be confirmed with the owner rather than assumed, and it is the first
open question.

### 3.7 Rate limits table

`dynamodb.tf` gains `<prefix>-rate-limits` with a TTL attribute, as layer 2 of the
rate limiting standard. The limiter fails open: a Dynamo error allows the request
rather than rejecting it, because a rate limiter that takes the site down when it
breaks is worse than no rate limiter.

This replaces the current limiter, which has three independent problems and
should be fixed early and separately from the split, because all three are live
bugs rather than migration concerns.

It is in-memory, so it keys per execution environment and is diluted by
concurrency and reset by every cold start. It keys on the leftmost
`X-Forwarded-For` hop, which the caller supplies and can therefore set to
anything. And it is currently disabled for every request in production: the skip
list in `rate_limiter.py` is tested with `startswith`, and it contains `"/"`,
which every path begins with. The condition is unconditionally true. That is why
`ENABLE_RATE_LIMITING` being `True` and all eight tier settings being configured
has had no observable effect.

The test suite cannot catch this. `test_rate_limiter.py` asserts that skipping
happens for `/health` and `/docs`, and never asserts that a normal path is
limited, so the bug is invisible to a green run. The fix is exact matching rather
than `startswith`, plus the missing negative test, and it should land with PR 3
rather than waiting for the shared limiter.

The replacement keys on the API Gateway request context identity, which the
caller cannot forge, and stores counters in the `<prefix>-rate-limits` table so
the limit is shared across execution environments and across the nine
functions.

---

## 4. CI and CD

`.github/workflows/deploy-backend.yml`, replacing `backend-deploy.yml`'s build
half while leaving its zip chain intact until the monolith retires.

Job chain: `resolve-env` then `build-images` then `image-map` then `deploy-images`
then `smoke-domains`, with the legacy zip `deploy` job independent of all of them.

The org reusable workflows are `container-image.yml` at v1.2.1 and
`lambda-image-deploy.yml`. Both already carry the fixes Portfolio needed.

**`resolve-env`.** A small job whose only purpose is to carry `environment:` and
export `vars.AWS_DEPLOY_ROLE_ARN` as an output. It exists because `environment:`
is not legal on a job that also carries `uses:`, and putting it there fails in a
way that is easy to miss: the job runs, the environment's variables are simply
absent, and the deploy silently targets nothing. Portfolio lost an hour to this
on staging, with actionlint reporting it correctly and the report dismissed. Run
actionlint on this workflow and believe it.

**`build-images`.** A matrix over the nine domains calling `container-image.yml@v1.2.1`
with `DOMAIN` as a build argument. Four things it must be given:

- The CodeArtifact token as a **BuildKit secret input**, not a build argument.
- `additional-ecr-registries` naming `432410731887`. The ECR login action
  authenticates only against the caller's own registry, so without this the base
  image pull from the artifacts account fails with an unhelpful auth error.
- `skip-if-tag-exists`, because the repositories are IMMUTABLE and a re-run of a
  workflow for the same commit would otherwise fail the push. The guard must use
  `aws ecr batch-get-image`, not `describe-images`: `describe-images` returns
  metadata that can be present for a tag that has no manifest, so it reports a
  false positive and the deploy then points a function at nothing.
- `upload-manifest-artifact`, so each matrix leg's digest is recoverable.
  A matrix cannot set a distinct output per leg, so the digests come back as
  uploaded artifacts and `image-map` assembles them.

**`image-map`.** Downloads the nine manifests and builds the domain-to-image-URI
map that the deploy job consumes.

**`deploy-images`.** Calls `lambda-image-deploy.yml` with that map. It runs the
HCP Terraform wait **once**, in a single gate before the deploys, not once per
domain: nine matrix legs each polling the same workspace is nine times the API
calls and, worse, each leg can observe a different terminal state as runs queue.
Build and push all nine images first, then take the gate, then run the nine
`UpdateFunctionCode` calls in quick succession, so the window an apply can race
holds only the update calls.

**`smoke-domains`.** The reusable deploy workflow's own smoke test hits the
function through the API, which does not work for a domain that has not been
routed yet. Instead, `aws lambda invoke` with a synthesised API Gateway HTTP API
v2 payload against `/health`, per domain. This is what needs the
`lambda:InvokeFunction` grant from section 3.2.

**Gates.** `BACKEND_IMAGE_BUILD_ENABLED` gates `build-images` and
`BACKEND_IMAGE_DEPLOY_ENABLED` gates `deploy-images`, both as repository
variables, so the image path can be built and verified in staging without
deploying, and can be switched off entirely without reverting the workflow.

**Prod images are rebuilt on main, not digest-copied** from staging. The tradeoff
is accepted: a rebuild is not bit-identical to what was tested, but a digest copy
across accounts needs cross-account ECR replication or a pull-push through the
runner, and both are more moving parts than a rebuild from the same commit.

The `docs/**` path triggers nothing. Every workflow has an explicit `paths:`
filter naming only `backend/**`, `frontend/**`, `chrome-extension/**`, and its own
file. This document's own PR deploys nothing, and neither does a `terraform/**`
change, since infrastructure applies through HCP Terraform's VCS integration
rather than Actions.

---

## 5. Observability

**OpenTelemetry to X-Ray, replacing Sentry, domain by domain.** OTLP over
http/protobuf, `OTEL_PYTHON_DISTRO=aws_distro`,
`OTEL_PYTHON_CONFIGURATOR=aws_configurator`. The Lambda role already carries
`xray:PutTraceSegments` and `PutTelemetryRecords`; `attach_xray_write_policy`
on the module makes it explicit per domain.

Sampling: 100 percent on staging, 10 percent on production, errors always sampled
regardless of the rate. The current Sentry `_traces_sampler` already forces
`/health` and `/ready` to zero, and that carries over.

Initialisation is lazy. Eagerly constructing the OTel SDK at import adds
meaningful cold-start time, and it would be paid nine times instead of once. The
tracer provider is built on first use, behind the same lazy pattern Portfolio
adopted.

Sentry is removed one domain at a time rather than all at once, so that at any
moment the cut domain reports through OTel and everything still on the monolith
reports through Sentry. `init_sentry()` currently runs at module level in
`main.py` **before** `FastAPI()` is constructed, deliberately, so the Starlette
integration can patch the handlers. Root B has no equivalent call and does not
need one.

Two Sentry facts worth recording before it goes. `SENTRY_SERVICE_NAME` is
`lambda-api` in Terraform but `init_sentry` is called with
`server_name="apprunner-backend"`, a leftover from App Runner, so the service name
in Sentry has been wrong. And `sentry.py`'s docstring claims a SQLAlchemy
integration that does not exist, from before the DynamoDB migration. Neither
matters once Sentry is gone, but both explain confusing historical data.

**Structured logging** stays as it is: `python-json-logger`, `log_format = "JSON"`
on the function, `application_log_level = "INFO"`. The service name in the log
context becomes `carmodpicker-<domain>`. Retention drops from 14 days to 7 on
both the function log groups and the API Gateway access log, which is a real
tradeoff: it shortens the debugging window on exactly the deploys most likely to
need it. It is accepted because nine log groups at 14 days is more than twice the
storage of one, and because the errors that matter are alarmed on rather than
found by scrolling.

**Dead code to delete on the way through.** `app/core/cloudwatch_emf.py` has no
call site anywhere; `emit_crawler_run_metrics` refers to a crawler tree that no
longer exists. `error_handler_middleware` is defined and never registered, since
`main.py` uses `register_error_handlers` instead. `configure_root_logging` is
never called, because `main.py` inlines an equivalent. None of these are load
bearing and all three are confusing to read.

There is no CloudWatch dashboard today and none is proposed. The aggregate alarms
plus X-Ray service map cover what a dashboard would show.

---

## 6. Cutover sequence

### 6.1 Order

Ordered by coupling, not by size. The five domains with no cross-domain write go
first, then the event plumbing, then the four that depend on it.

1. `media` (8 routes). Smallest, and the only one holding bucket-wide S3 grants,
   so it proves the IAM split is real. Uses Pillow, so it also proves `arm64`.
2. `build-logs` (5). Genuinely self-contained.
3. `moderation` (20). Cuttable early only because seam 3 lands with it, moving
   the `net_votes` write to `catalog`'s side of the stream.
4. `vehicles` (11). Read-only, no secret, cheapest possible IAM.
5. `ingestion` (12). Gains the price-alert handler from seam 4.
6. Event plumbing: tombstones, streams, queues, and the tombstone-aware read
   paths in `build-lists`, `build-logs`, `moderation`, and `vehicles`.
7. `build-lists` (34).
8. `identity` (24).
9. `catalog` (43). Depends on the plumbing for the part purge.
10. `users` (14). Last. The hardest coupling, and by the time it moves every
    consumer of the tombstone is already handling it.
11. Retire `$default`, the monolith, the artifacts bucket, and the zip chain.

### 6.2 Cutting the first domain

`media` on staging, in this order:

1. Merge the source layout and the per-domain repository bundles. Green suite,
   nothing deployed.
2. Merge the route contract test. It locks all 176 routes before anything moves.
3. Build and push the `media` image. Nothing is routed; the image exists.
4. Terraform creates the `media` function from the bootstrap tag. Nothing is
   routed; the function exists and answers `aws lambda invoke` on `/health`.
5. Add the two API Gateway routes. This is the cut. `/api/images` now resolves to
   the `media` function; everything else still resolves to `$default`.
6. Watch for a day.

### 6.3 Verifying a flip

The access log format includes `routeKey`, which is what makes a flip verifiable
rather than assumed. Before the cut every entry reads `$default`; after it,
requests to the cut prefix read the explicit route key. Grepping the access log
for the prefix and confirming no `$default` entries remain for it is the check.

Alongside that: the domain function's invocation count goes from zero to the
prefix's traffic, the monolith's drops by the same amount, and the error rate on
both is unchanged. If the monolith's invocation count does not drop, the route
did not take effect. If both are serving the prefix, one of the two route keys is
missing and half the endpoints are still on `$default`.

### 6.4 Rollback

Delete the two route keys for the domain and apply. `$default` resumes serving
the prefix within seconds, because the monolith still contains every domain's
code for the entire migration. There is no data to unwind and no image to revert.

That is the reason the monolith keeps every domain's code until the very end
rather than having code removed as each domain is cut. It costs a larger zip and
the risk that the two roots drift, and it buys a rollback that is one Terraform
apply with no coordination.

The drift risk is managed by the contract test: both roots are built from the
same domain packages, and the test asserts their route sets are identical.

### 6.5 Retiring the monolith

Only after every domain has run in production long enough to trust. Then, in one
PR: remove `$default`'s integration, delete `module.lambda_api` and its four
inline policies, delete `app/lambda_handler.py` and the `lambda_placeholder`
directory, delete the zip build from the workflow, delete
`module.lambda_artifacts` and the artifacts bucket, and drop the
`s3:PutObject` grant from the deploy role.

Retiring the monolith frees the tenth slot in `lambda_function_names`.

---

## 7. Data

**No table migrations.** DynamoDB stays, all 25 tables keep their keys, indexes,
and names. The split is a compute change.

**Two schema additions.** A tombstone pair, `deleted` and `deleted_at`, on `users`
and on `parts`. Both are new attributes on existing items, so existing rows simply
lack them and read as not deleted. No backfill.

**Streams get enabled** on `users`, `parts`, `votes`, and `part_listings`, with
`NEW_AND_OLD_IMAGES`, feeding one SQS queue per subscribing domain. Streams are
not configured on any table today, and `dynamodb_tables.json` carries no stream
field, so this is an addition to the module call rather than a per-table edit.

Each queue gets a dead letter queue. A cleanup handler that fails repeatedly must
not silently drop a delete, because the visible symptom is a user who deleted
their account and whose build lists are still public.

**Ordering and idempotency.** DynamoDB streams guarantee order per partition key,
which for these tables is the item id, so all events for one user or one part
arrive in order. They do not guarantee exactly-once delivery, so every cleanup
handler must be idempotent. Deleting a row that is already gone is a no-op in
Dynamo, so this is close to free, but the handlers must not, for example,
decrement a counter per event.

**PITR** is production-only today and stays that way. It covers the new attributes
automatically.

**The `part_cars` table** is the only composite-key table, hash `part_id` and
range `car_id`, and it is worth noting for the purge handler: deleting a part's
rows there is a query then a batch delete, not a single delete.

**No cursor state spans functions.** Pagination is offset-based throughout,
`skip` and `limit`, so no continuation token has to survive a domain boundary.

**The seed task needs an owner.** `init_car_generations()` runs from the `main.py`
lifespan under `RUN_STARTUP_TASKS`, which Terraform sets to `false` on Lambda, so
it does not run in production today. Left as it is in the new layout, it would
either stay off everywhere, or, if switched on, have nine cold starts racing the
same seed writes. It belongs in `vehicles` behind an explicit admin route or a
one-off job, and `admin/db_ops` already has the equivalent endpoints.

---

## 8. PR list

Sizes: small under 200 lines changed, medium 200 to 800, large above 800.
"Expected plan" is the Terraform plan delta, where zero means the PR touches no
infrastructure.

| # | PR | Size | Expected plan | Depends on |
|---|---|---|---|---|
| 1 | This plan and the inventory amendments | small | 0 | none |
| 2 | Fix `/api/part-price-alerts/unsubscribe` route ordering | small | 0 | none |
| 3 | Rate limiting layer 2: `<prefix>-rate-limits` table and the shared limiter | small | 1 add | none |
| 4a | Backend: both composition roots, no files moved | large | 0 | none |
| 4b | Backend: physical move of the endpoint modules into `app/domains/<domain>/` | large | 0 | 4a |
| 5 | Backend: route contract test locking all 176 routes | small | 0 | 4a |
| 6 | Backend: unwind the `Repositories` singleton into per-domain bundles | large | 0 | 4a |
| 7 | Backend: lazy secret resolution in `config.py` | medium | 0 | 4a |
| 8 | `webbpulse` package adoption: logging, tracing, settings base | medium | 0 | 4a |
| 9 | Terraform: nine ECR repositories per environment | small | 18 add per env | none |
| 10 | Terraform: deploy role gains ECR push, widened Lambda, `InvokeFunction` | small | 1 change | 9 |
| 11 | Dockerfile, parameterised by `DOMAIN` | medium | 0 | 4a, 6 |
| 12 | `deploy-backend.yml`: `resolve-env`, `build-images`, `image-map`, `deploy-images`, `smoke-domains` | medium | 0 | 10, 11 |
| 13 | Terraform: `media` function from the bootstrap tag, unrouted | medium | 3 add | 12 |
| 14 | Terraform: `media` API Gateway routes. **First cut** | small | 3 add | 13 |
| 15 | Terraform: alarms to `api-alarms ~> 2.1`, `lambda_function_names` | small | 6 change | 14 |
| 16 | Observability: OpenTelemetry in `media`, Sentry removed from it | medium | 1 change | 14 |
| 17 | Terraform: log retention 14 to 7 days | small | 2 change | 15 |
| 18 | `build-logs`: function, routes, OTel | medium | 6 add | 16 |
| 19 | `moderation`: function, routes, OTel | medium | 8 add | 18 |
| 20 | `vehicles`: function, routes, OTel | medium | 7 add | 19 |
| 21 | `ingestion`: function, routes, OTel | medium | 11 add | 20 |
| 22 | Streams on `users`, `parts`, `votes`, `part_listings`, plus queues and DLQs | large | 16 add | 21 |
| 23 | Tombstone attributes and tombstone-aware reads in four domains | large | 0 | 22 |
| 24 | Seam 3: `net_votes` handler moves to `catalog`'s stream consumer | medium | 2 add | 22 |
| 25 | Seam 4: price alert email moves to an `ingestion` stream handler | medium | 2 add | 22 |
| 26 | `build-lists`: function, routes, OTel | large | 10 add | 23 |
| 27 | `identity`: function, routes, OTel | medium | 4 add | 23 |
| 28 | Seam 2: part purge goes async | large | 2 add | 23 |
| 29 | `catalog`: function, routes, OTel | large | 10 add | 28 |
| 30 | Seam 1: user delete cascade goes async | large | 5 add | 23, 29 |
| 31 | `users`: function, routes, OTel. **Ninth cut, alarm list full** | large | 5 add | 30 |
| 32 | Retire `$default`, the monolith, the artifacts bucket, the zip chain | medium | 12 destroy | 31 |
| 33 | Frontend: delete the `services/Api.ts` shim, rewriting 74 import sites | medium | 0 | none |

**PR 4 ships in two slices, and 4a is delivered.** The original row bundled two
unrelated changes: introducing the composition roots, and moving every endpoint
module on disk. Together they produce a diff in which a genuine wiring change is
indistinguishable from a rename, so the two are separated.

- **4a, delivered.** `app/composition/` holds the shared wiring, the nine domain
  descriptors and Root A; `app/entrypoints/<domain>.py` is Root B, one module per
  deployed function. `app/main.py` becomes a thin re-export of Root A and no
  other module moves or is renamed. The route contract, the per-domain counts and
  the isolation properties are asserted by `backend/tests/entrypoints/`, and the
  published OpenAPI document is byte-identical to the one `staging` serves.
- **4b, later.** The physical move of `app/api/endpoints/<module>.py` into
  `app/domains/<domain>/`. Because 4a already records each domain's modules in
  one place, 4b is a move plus an import rewrite, reviewable as such.

Every row that depended on "4" depends on 4a: what PRs 6, 7, 8 and 11 need is the
domain boundary expressed in code, not the directory layout. Only 4b needs 4b.

PRs 1, 2, 3, 9, 10, and 33 are independent of everything else and can run in
parallel. PR 22 is the hard gate: nothing from 23 onward can start without it,
which is why the five uncoupled domains are cut first, buying time for the
plumbing to be built and observed.

The expected-plan numbers are estimates for catching surprises, not commitments.
A plan that differs by one or two is normal; a plan that differs by ten means
something else changed.

---

## 9. Open questions

Ranked. The first three block work; the rest can be answered as their PR comes
up.

**1. The alarm ceiling.** Section 3.6 recommends keeping `lambda_function_names`
at ten as the fast Lambda-level signal and letting the log-based
`application-errors` alarm scale past it, since it is dimensionless. The
alternative is two aggregate alarms over two groups of five, which removes the
ceiling but weakens the signal from "the backend is erroring" to "group A is
erroring". This needs a decision before PR 15, and it is the only one of these
that constrains the architecture rather than the schedule.

**2. `net_votes` eventual consistency.** Seam 3 makes the denormalised vote count
lag the vote by the stream latency, so a user who votes and immediately reloads
may see the old number. Accept the lag, or change the vote route to return the
computed count and have the frontend use the response rather than re-reading?
The second is a small frontend change and removes the problem, but it is a
frontend change in the middle of a backend migration.

**3. The two unauthenticated write routes.** `POST /api/parts/{part_id}/listings`
and `POST /api/parts/price-history` take no user dependency, unlike every other
mutating route. Both are presumably for the Chrome extension, which does hold a
bearer token and could send it. Is this deliberate? If not it should be fixed
before `catalog` is cut, not as part of it, so the fix is reviewable on its own.

**4. Renaming `ingestion`.** It holds price alerts and two admin modules, and
`crawled_pages` touches no repository. `admin` describes it better. Cheap now,
expensive after the first cut, because the name is in the ECR repository, the
function name, the image tag, and the log group.

**5. The `vehicles` boundary.** Search fanning out over four domains sits there
because `vehicles` would otherwise be the smallest domain. Section 1.5 argues it
is the least bad of three options, but it is the weakest boundary in the map.

**6. The orphan sweep.** Five full table scans behind an admin HTTP route in a 29
second Lambda. It will time out as the tables grow. Move it to a scheduled job
now, or leave it and accept that it breaks later?

**7. `arm64`.** Recommended, matching Portfolio and the base image. Needs
`Pillow`, `bcrypt`, and `webauthn` verified, which PR 13 does by building `media`
first. Confirm the intent before that PR.

**8. Log retention 14 to 7 days.** A real loss of debugging window in exchange
for storage across nine log groups. Confirm it is wanted.

**9. Frontend and extension routing.** The plan keeps one edge hostname in front
of every function, so neither the frontend nor the extension needs a change. The
extension in particular stores its API origin as a single string in users' synced
browser profiles and derives the web origin from it by stripping `api.`, so
per-domain hostnames would need a store release and a migration list. Confirming
one hostname stays is confirming that no client work is needed.

**10. `pages/admin/SystemStatistics.tsx`.** It calls the `count` endpoint of
thirteen prefixes on load, so after the split it fans out to nine functions and
pays nine cold starts. Not a blocker, but it will be the most visibly slow page
in the application and someone will report it as a regression.
