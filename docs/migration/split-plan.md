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
| `admin` | `crawled_pages`, `part_price_alerts`, `admin/db_ops`, `admin/stats` | 12 | `/api/crawled-pages`, `/api/part-price-alerts`, `/api/admin/db-ops`, `/api/admin/stats` |

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
| `parts` | `catalog` | `moderation` (`net_votes` denormalisation), `users` (delete cascade), `admin` (`admin/db_ops`) |
| `part_cars` | `catalog` | `users` (delete cascade), `admin` |
| `part_listings` | `catalog` | `build-lists` (price capture), `users` (delete cascade) |
| `part_price_history` | `catalog` | `build-lists` (price capture), `users` (delete cascade) |
| `part_manufacturers` | `catalog` | `admin` |
| `categories` | `catalog` | `admin` |
| `retailers` | `catalog` | none |
| `car_makes` | `vehicles` | `admin` (seed and delete-all) |
| `car_models` | `vehicles` | `admin` |
| `car_generations` | `vehicles` | `admin` |
| `build_lists` | `build-lists` | `users` (delete cascade), `admin` |
| `build_list_parts` | `build-lists` | `catalog` (part purge), `users` (delete cascade) |
| `build_list_phases` | `build-lists` | `users` (delete cascade) |
| `build_list_labor_estimates` | `build-lists` | `users` (delete cascade) |
| `build_logs` | `build-logs` | `build-lists` (created with the list), `users` (delete cascade) |
| `build_log_posts` | `build-logs` | `users` (delete cascade) |
| `votes` | `moderation` | `catalog` (part purge), `users` (delete cascade), `admin` |
| `reports` | `moderation` | `catalog` (part purge), `users` (delete cascade) |
| `bug_reports` | `moderation` | none |
| `part_price_alerts` | `admin` | `catalog` (part purge), `users` (delete cascade) |
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
`part_price_alerts`, owned by `build-lists`, `moderation` twice, and `admin`.
Same mechanism, smaller blast radius: a tombstone on `parts` plus a stream, with
`build-lists`, `moderation`, and `admin` each draining their own queue.

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
`part_price_alerts` belongs to `admin`.

This one is the easiest to fix and the most worth fixing on its own merits, split
or no split. Today a price write blocks on a fan-out read plus an SES call inside
a 29 second Lambda, and there is no scheduler behind it: alerts fire only when
some request happens to write a price. It becomes a stream on `part_listings`
feeding an `admin` handler that owns both the alert rows and the SES send.
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
| `/api/part-price-alerts/unsubscribe` vs `/{alert_id}` | `admin` | Survives only because `/{alert_id}` is PATCH and DELETE and there is no GET detail route. Fragile: adding `GET /{alert_id}` breaks unsubscribe silently |
| `/api/build-list-parts/parts/{part_id}/build-lists/count` vs `/{build_list_id}` | `build-lists` | Three-segment shape differs. A bare `/api/build-list-parts/parts` would match `{build_list_id}` |
| `/api/users/admin/users` vs `/{user_id}` | `users` | Two segments. A bare `/api/users/admin` would match `{user_id}` |
| `/api/build-lists/with-votes`, `/count`, `/car/{id}`, `/user/me` vs generated `{entity_id}` | `build-lists` | Literals registered first |

The `part-price-alerts` row is the one to fix rather than document. It is one
route away from a silent production break, and the fix is to register
`/unsubscribe` before the parameterised routes. That is a two-line change and
should go in early, independent of the split.

There is one genuine cross-domain ordering conflict and it is in the API Gateway
map rather than in FastAPI. `admin` serves `/api/admin/db-ops` and
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

`admin` was called `ingestion` until the rename below, and the old name was the
weaker of the two. `crawled_pages` is one route that touches no repository at
all; it parses HTML the Chrome extension posts and returns the result. The
listing writes that "ingestion" implies belong to `catalog`. What is actually in
the domain is the price alerts and the two admin modules, which is a coherent
function and an administrative one. The boundary itself never moved; only the
name did.

The count the code would argue for, left to itself, is seven: fold `search` into
`catalog`, fold `build-logs` into `build-lists`, and fold `admin`'s modules
into the domains they administer. That is rejected because it makes
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
    admin.py
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

**The repository half is unwound; PR 6 delivered it.**
`app/api/dependencies/repositories.py` used to define a frozen dataclass
`Repositories` that instantiated all twenty-five repositories at module import,
and `get_repositories()` returned it. Every route in the application depends on
it, so left as it was, every one of the nine functions would have imported all
twenty-five repository modules, and through them the entire data layer, on every
cold start.

What replaced it is a per-domain repository bundle. `app/db/dynamo/registry.py`
records each repository's defining module, class and table as strings, so reading
the catalogue costs no import. `RepositoryBundle` carries a declared set of names
and builds each one on first access; an access outside the set raises
`RepositoryNotInBundle`, which names the domain, the repository and the table so
the next question, which IAM grant is missing, is already answered.
`app/composition/domains.py` gives each domain a `repositories` tuple, Root B
builds a bundle from one domain's tuple and Root A from all twenty-five, and
`bind_repositories` installs it in that application's `dependency_overrides`
rather than in a process global, so nine applications can be built side by side
in one interpreter. The route signatures did not change: `Repositories` is still
the annotation on roughly two hundred call sites, now aliased to the bundle, so
the OpenAPI document is byte-identical. A `media` process imports five repository
modules instead of twenty-five and never imports `app.db.dynamo.app_settings` at
all; `backend/tests/entrypoints/test_repository_bundles.py` asserts that in a
fresh interpreter and checks each domain's declared bundle against the
repositories its own routes actually reach.

**The config half is delivered too; PR 7 shipped it.** `app/core/config.py`
used to call `load_app_secrets()` at import time, so every function would have
needed `secretsmanager:GetSecretValue` at cold start whether or not it used a
secret. Portfolio solved this by making secrets optional fields resolved lazily
through a `_resolve_secret` helper, with a `require_secrets()` call at the point
of use rather than a validator that raises at import. The same change is now in
place here, and it is what lets `vehicles`, which is entirely read-only and needs
no secret, drop the grant.

This was sharper than it sounded. Importing `app.core.config` used to perform a
network call to Secrets Manager and re-raise on failure, which made the module
un-importable without AWS credentials. Any tooling that imports the application
without credentials failed, and that includes the contract test in section 2.7,
which has to import all nine Root B applications. So the lazy resolution was not
an optimisation, it was a prerequisite for the test that makes every cut
verifiable.

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

**Delivered by row 11.** The sketch below is what was designed; section 8's row
11 paragraph records the three places the shipped file departs from it, the
`PORT` one being the only one that would have cost a debugging session.

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

The variable also takes the empty string, and that is what makes this root
promotable to an account where no image has ever been pushed. Empty resolves
`local.lambda_domains` to empty, and `local.routed_lambda_domains` in
`apigateway.tf` is filtered on the same set, so the apply builds the
repositories and everything else and creates no function and cuts no route.
Section 6.6 has the full sequence.

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

Three domains have grants beyond Dynamo. `identity` and `admin` get
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
| `admin` | `/api/crawled-pages`, `/api/part-price-alerts`, `/api/admin/db-ops`, `/api/admin/stats`, each with a pair |
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

`monitoring.tf`. `api-alarms` is already at `~> 2.4`, and `lambda_function_name`
becomes `lambda_function_names`, a list. Aggregate on:
`lambda_aggregate_alarm = true`, `lambda_aggregate_threshold = 0`.
`dynamodb_aggregate_alarm = true` stays as it is. `error_log_groups` becomes a
merge of the monolith's log group and the created domains'. The list itself
holds the domains only and not the monolith; the paragraph on row 15 below says
what that costs and why it is still right.

The list order matters and is not cosmetic. The module builds CloudWatch metric
math over positionally-named metric ids, `m0`, `m1`, and so on, so reordering the
list rewrites every expression and replaces the alarm. Fix the order once, in the
same order as `local.lambda_domain_names`, and add a comment saying so. The
ordered list and not `local.lambda_domains`: the latter is a map, and `keys()` on
it returns lexicographic order rather than cut order, so it reshuffles every
metric math id whenever a domain lands mid-alphabet.

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

### Transaction Search, the OTLP prerequisite

2026-09-07. Enabled in Terraform, in `terraform/transaction_search.tf`, because
AWS requires it before the X-Ray OTLP endpoint will accept spans: "If you are
using traces, make sure Transaction Search is enabled to send spans to the X-Ray
OTLP endpoint." It is the prerequisite for the collector-less export described
above, and it lands ahead of the domain carve-outs that point the functions at
the endpoint.

Three resources: a CloudWatch Logs resource policy letting `xray.amazonaws.com`
write to `aws/spans`, the trace segment destination set to `CloudWatchLogs`, and
the `Default` indexing rule at 1 percent.

It goes in as a two-step sequence. Terraform cannot create the `aws/spans` log
group ahead of X-Ray, because names starting with `aws/` are reserved and
CreateLogGroup rejects them, so the group does not exist until the destination
flips and X-Ray writes to it for the first time. Step one is this file as it
stood at first: the resource policy, the destination, and the indexing rule. X-Ray
then creates `aws/spans` with its own 30 day default. Step two, applied on staging
on 2026-09-08 once the group existed, is the `import` block and
`aws_cloudwatch_log_group.spans` resource that adopt the group and put the
platform's standard 7 day retention on it.

Step two is gated on `var.adopt_spans_log_group`, which defaults to `true`. An
import block whose target does not exist is a plan time error, not a skipped
no-op, so leaving it unconditional would make the very first apply in a fresh
account fail at plan: the destination flip and the import would be in the same
run, and no span has been written yet. Both the import and the resource carry a
`for_each` over a set of at most one name, so the flag adds and removes them
together, and a `moved` block carries the previously unkeyed
`aws_cloudwatch_log_group.spans` to `["aws/spans"]` so the refactor is a state
move rather than a destroy and a create. A fresh account applies with the flag
`false`, generates a span, and then sets it `true`; section 6.6 has the
sequence.

Two things worth knowing. It is account-wide for the region rather than per
environment, so it changes trace storage for everything in the account that
writes segments, not only the CarModPicker functions. And spans are stored as
structured logs in `aws/spans` under CloudWatch Logs pricing rather than as X-Ray
traces, with 1 percent of traceIds indexed for trace summaries, which is the free
tier and the AWS default. The account's `Default` rule reads 0 percent today, so
the first apply raises it.

Neither X-Ray resource reverts anything when it is removed from Terraform, so
turning this back off is an explicit change of the destination to `XRay` and not
a destroy.

The provider bump this needed, `~> 5.0` to `~> 6.46`, is what made those two
X-Ray resources available: both were added in 6.46.0.

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
5. `admin` (12). Gains the price-alert handler from seam 4.
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

### 6.6 Promoting to a fresh account

Everything above assumes an account that already has ECR repositories with
images in them and an `aws/spans` log group that X-Ray has created. A brand new
production account has neither, and both are ordering problems that no single
apply can solve: a function cannot be created before its image exists, the image
cannot be pushed before its repository exists, and `aws/spans` cannot be created
by Terraform at all because `CreateLogGroup` rejects names beginning with
`aws/`.

Two variables carry the bootstrap, and both default to the settled state so an
environment already past this sees nothing:

- **`bootstrap_image_tag`**, in `terraform/lambda_domains.tf`. The empty string,
  which is the default, means "this account has no images yet": it resolves
  `local.lambda_domains` and `local.routed_lambda_domains` to empty, so the
  apply creates no domain function and cuts no route. A `sha-<40 hex>` value
  means the images are there and the functions should be built from that tag.
- **`adopt_spans_log_group`**, in `terraform/transaction_search.tf`. `true`, the
  default, imports the reserved `aws/spans` group and holds it at 7 days.
  `false` skips both the import and the resource, which is what a fresh account
  needs on its first apply, because an import block whose target does not exist
  is a plan time error rather than a skipped no-op.

The sequence, in order. Nothing here needs a throwaway PR and no step is a
knowingly failing apply.

**1. Set the two bootstrap variables on the new workspace.** Both as Terraform
variables, neither sensitive:

```
bootstrap_image_tag  = ""
adopt_spans_log_group = false
```

Set every other workspace variable the environment needs at the same time:
`environment`, `aws_region`, and the sensitive `secret_key` and `sentry_dsn`.

**2. Apply.** This creates the nine ECR repositories, every IAM role including
the CodeArtifact statements the deploy and CI roles need, the DynamoDB tables,
the buckets, the secret, the HTTP API with the monolith on `$default`, the
Transaction Search resource policy and destination and indexing rule, and the
alarms. It creates no domain function, cuts no route, and creates no aggregate
Lambda alarm, because there is nothing yet for that alarm to sum. Verify: the
nine repositories exist and are empty, and the deploy role carries the
CodeArtifact grants.

**3. Dispatch `Deploy Backend`** (`.github/workflows/deploy-backend.yml`) on the
target branch, with `BACKEND_IMAGE_BUILD_ENABLED` set. The nine repositories now
exist, so the build pushes nine images tagged `sha-<commit sha>`. The
`existing-functions` job finds no functions and drops all nine from the image
map, `deploy-images` skips on the empty map, and `smoke-domains` and
`verify-route-cuts` skip with it, so the run is green. Verify: nine
`sha-<commit sha>` tags across the nine repositories. Use the commit sha the
build actually ran on, not whatever the branch points at afterwards.

**4. Set `bootstrap_image_tag` to that exact `sha-<commit sha>`** on the
workspace.

**5. Apply again.** This creates every domain function in
`local.lambda_domains_declared`, its role, its log group, its two policies and
its runtime policy, the API Gateway integration and permission and the two route
keys per prefix for every domain in `local.routed_lambda_domains_declared`, the
two metric filters per function, and the aggregate Lambda alarm pair. Functions
and routes land in the same apply on purpose: `verify-route-cuts` hardcodes its
domain list, so a function that exists without its routes makes that job probe
the prefix, read `routeKey: $default`, and exit 1.

**6. Dispatch `Deploy Backend` again**, with `BACKEND_IMAGE_DEPLOY_ENABLED` set.
`existing-functions` now finds the functions, `deploy-images` points each at its
digest, `smoke-domains` probes them and `verify-route-cuts` checks the cuts.
Verify: `verify-route-cuts` passes.

**7. Generate one span, then adopt `aws/spans`.** Any request that reaches a
domain function will do; the first export creates the group with X-Ray's own 30
day default. Confirm the group exists, then set `adopt_spans_log_group = true`
and apply a third time. That apply is one import and one retention change from
30 days to 7. Verify: `aws_cloudwatch_log_group.spans["aws/spans"]` is in state
at 7 days.

Steps 1 through 6 are two applies and two workflow dispatches, and step 7 is a
third apply that can happen whenever traffic has produced a span. None of them
is expected to fail.

Reverting is the same two variables. Clearing `bootstrap_image_tag` back to `""`
would destroy every domain function and route, which is a real rollback rather
than a bootstrap step, and `adopt_spans_log_group = false` would drop the group
from state without deleting it in AWS.

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
| 13 | Terraform: `media` function from the bootstrap tag, unrouted. **Delivered** | medium | 5 add (recorded 3 at the time; see the per-cut anatomy below) | 12 |
| 14 | Terraform: `media` API Gateway routes. **First cut** | small | 4 add | 13 |
| 15 | Terraform: alarms to `lambda_function_names`, aggregated. **Delivered** | small | 3 add, 1 change, 2 destroy | 14 |
| 16 | Observability: OpenTelemetry in the domain functions, Sentry removed from them. **Delivered** | medium | 1 change | 14 |
| 17 | Terraform: log retention 14 to 7 days. **Delivered** | small | 2 change | 15 |
| 18 | `build-logs`: function, routes, OTel. **Delivered** | medium | 11 add, 4 change | 16 |
| 19 | `moderation`: function, routes, OTel. **Delivered** | medium | 15 add, 4 change | 18 |
| 20 | `vehicles`: function, routes, OTel | medium | est. 13 add, 4 change | 19 |
| 21 | `admin`: function, routes, OTel | medium | est. 17 add, 4 change | 20 |
| 22 | Streams on `users`, `parts`, `votes`, `part_listings`, plus queues and DLQs | large | 16 add | 21 |
| 23 | Tombstone attributes and tombstone-aware reads in four domains | large | 0 | 22 |
| 24 | Seam 3: `net_votes` handler moves to `catalog`'s stream consumer | medium | 2 add | 22 |
| 25 | Seam 4: price alert email moves to an `admin` stream handler | medium | 2 add | 22 |
| 26 | `build-lists`: function, routes, OTel | large | est. 17 add, 4 change | 23 |
| 27 | `identity`: function, routes, OTel | medium | est. 11 add, 4 change | 23 |
| 28 | Seam 2: part purge goes async | large | 2 add | 23 |
| 29 | `catalog`: function, routes, OTel | large | est. 17 add, 4 change | 28 |
| 30 | Seam 1: user delete cascade goes async | large | 5 add | 23, 29 |
| 31 | `users`: function, routes, OTel. **Ninth cut, alarm list full** | large | est. 13 add, 4 change | 30 |
| 32 | Retire `$default`, the monolith, the artifacts bucket, the zip chain | medium | 12 destroy | 31 |
| 33 | Frontend: delete the `services/Api.ts` shim, rewriting 74 import sites | medium | 0 | none |

**Rows 19 through 31 are estimates, and the arithmetic behind them is worth
stating rather than hiding.** Row 18's delivery note found the per-cut shape by
counting a real plan, and rows 13, 14 and 15 had each recorded only the part of
it they were looking at. Written out, one domain cut is:

- **Five resources for the function.** The module's `aws_lambda_function.this`,
  `aws_iam_role.this`, `aws_cloudwatch_log_group.this` and
  `aws_iam_role_policy.xray_write[0]`, plus this repository's own
  `aws_iam_role_policy.lambda_domain[<domain>]`. Row 13 wrote 3 for this shape
  because it counted the function, the role and the runtime policy and missed
  the module's log group and X-Ray policy. Five is the number.
- **Two resources for the integration.** One
  `aws_apigatewayv2_integration.this[<domain>]` and one
  `aws_lambda_permission.this[<domain>]`, once per domain regardless of how many
  prefixes it serves.
- **Two routes per path prefix**, the bare key and the `{proxy+}` key, from the
  "Path prefixes served" column of section 1.1.
- **Two metric filter adds**, `errors[<domain>]` and
  `rate_limit_failed_open[<domain>]`, the new log group joining the two
  log-based alarms.
- **Four alarm changes.** The two description strings that count log groups on
  `errors[0]` and `rate_limit_failed_open[0]`, and the two aggregate alarms
  whose description counts functions and whose metric math appends one term.

So a cut is `5 + 2 + 2*prefixes + 2` adds and 4 changes. `moderation` serves 3
prefixes, `vehicles` 2, `admin` 4, `build-lists` 4, `identity` 1, `catalog` 4
and `users` 2, which is where the numbers in the table come from. They are
estimates rather than counted plans, and each row's delivery note should record
what it actually saw. The seam and stream rows (22, 24, 25, 28, 30) are not
cuts and their counts are unchanged.

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

**Row 6 is delivered.** `app/db/dynamo/registry.py` is the catalogue of the
twenty-five repositories, holding each one's defining module, class and table as
strings so reading it constructs nothing and imports nothing.
`app/api/dependencies/repositories.py` is now a `RepositoryBundle` that carries a
declared set of those names and builds each on first access; an access outside
the set raises `RepositoryNotInBundle`, naming the domain, the repository and the
table. Each of the nine descriptors in `app/composition/domains.py` carries a
`repositories` tuple, and `bind_repositories` installs a domain's bundle in that
application's `dependency_overrides` rather than in a process global, so Root A
still carries all twenty-five and the nine Root B applications can be built side
by side in one interpreter. `Repositories` remains the annotation on roughly two
hundred call sites, so no route signature moved and the OpenAPI document is
byte-identical. `backend/tests/entrypoints/test_repository_bundles.py` compares
each domain's declared bundle against the repositories its own routes actually
reach, checks every table in section 1.2 against exactly one owning domain, and
proves in a fresh interpreter that building `media` constructs no repository and
imports no repository module outside its five.

**Row 7 is delivered.** Secrets resolve lazily in `app/core/config.py`, and
section 2.3 records what that changed.

**Row 8 is delivered, and it took less from the package than the row implied.**
`requirements.txt` now carries `webbpulse[fastapi,otel]==0.2.0`, which is
published only to CodeArtifact, so `backend-ci.yml` gained an OIDC role
assumption and an `aws codeartifact login --tool pip` step ahead of every
install. Three pieces moved: `webbpulse.logging.configure_logging` replaced the
hand-rolled `python-json-logger` setup, `Settings` now inherits
`webbpulse.config.BaseServiceSettings`, and every entrypoint's `main()` serves
through `webbpulse.lambda_entry.run_uvicorn`. `configure_tracing` is wired into
`build_domain_app` but gated: it returns immediately unless
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set, because the package otherwise falls
back to the X-Ray OTLP endpoint, which answers 403 without an IAM grant the
monolith does not have and which the exporter then retries in silence. Row 16 is
what sets the variable, per domain.

What did not move is the more useful half of the result. `webbpulse.http.create_app`
was evaluated and rejected: its exception handlers render
`{"success", "status", "message", "request_id"}`, and CarModPicker serves two
different shapes that the frontend and the Chrome extension parse. An unmatched
route returns Starlette's `{"detail": "Not Found"}`, because
`register_error_handlers` hooks `fastapi.HTTPException` and that does not catch
the bare routing exception; anything raised inside a route returns
`{"success", "message", "error_code"}` with no `detail` key at all. Adopting
`create_app` would have rewritten both, and it has no equivalent for the four
DynamoDB handlers either. Per the package gap policy the local implementation
stays and the divergence is a package problem to solve later, not a fork.
`tests/entrypoints/test_webbpulse_adoption.py` pins all three bodies exactly, so
a later adoption fails loudly rather than silently changing every error message
in the API. Two smaller pieces stayed for the same reason: `RequestContextFilter`,
which puts `request_id` and `user_id` on every record where the package merges
trace ids instead, and the stream choice, since the package logs to stdout and
CarModPicker has two commands whose stdout is data compared byte for byte.

The package is pinned in both requirements files, and a test now enforces that.
`requirements-lambda.txt` is what the deploy zip and row 11's per-domain image
install, and it is the narrower file on purpose, so a runtime dependency added
only to `requirements.txt` passes every check and then fails at import inside the
image. `tests/test_requirements_lambda_subset.py` asserts the Lambda file is a
strict subset with character-identical specifiers, extras included, which is what
catches `webbpulse[fastapi]` drifting from `webbpulse[fastapi,otel]`.

One thing is deliberately unfinished. `CI_AWS_ROLE_ARN` points at
`carmodpicker-staging-github-actions-deploy`, which already holds the
CodeArtifact grants and already trusts every subject in the repository, so CI
works with no Terraform change. It also holds `lambda:UpdateFunctionCode` and
`ecr:PutImage`, which means any branch that can open a pull request can assume a
role that can deploy. Row 10 already opens `terraform/iam_github_actions.tf`; the
fix is to add the read-only CI role there, as Portfolio did, and repoint the
variable.

**Row 11 is delivered.** `backend/Dockerfile` builds all nine images from one
file, with `ARG DOMAIN` selecting the entrypoint and no default, so an image
cannot silently be some other domain's. The domain name is mapped to its module
name at build time rather than at container start, because domain names carry
hyphens for ECR repositories, functions and log groups while Python modules must
carry underscores, and `build-lists` and `build-logs` are the two that differ;
the build then asserts that `app/entrypoints/<module>.py` is actually in the
image, which turns what would otherwise be a `ModuleNotFoundError` on a
deployed function's first cold start into a failed build.

Three things differ from what section 2.5 sketched, and each is a correction
rather than a preference. The install is `requirements-lambda.txt`, not
`requirements.txt`: the latter is the development set and carries `pytest`,
`moto`, `black`, `mypy`, `locust` and `curl_cffi`, and section 2.6 already
requires `curl_cffi` to stay out. PyPI stays configured as an extra index behind
the CodeArtifact one, so the build works whether or not the requirements yet
name `webbpulse`. That last prediction, that row 8 would change this file not at
all, turned out wrong in the one way that mattered: `webbpulse` is a runtime
dependency, so row 8 had to pin it in `requirements-lambda.txt` as well, and
until it did the image would have failed at import while every check passed.
`tests/test_requirements_lambda_subset.py` now enforces the relationship. And `PORT`
is set alongside `AWS_LWA_PORT`, because `Settings.PORT` defaults to 8000 and it
is the environment variable that overrides it; an entrypoint binding 8000 while
the adapter polls 8080 presents as a readiness check that never passes, with no
application logs to say why.

`AWS_LWA_READINESS_CHECK_PATH=/health` holds for all nine, as section 2.5
predicted: `/health` is a static dictionary and `/ready` is the one that calls
`check_db_ready()`, so no domain needs Portfolio's `tcp` fallback. All nine were
run under uvicorn against DynamoDB Local with the image's own environment and
the `requirements-lambda.txt` closure, and all nine bind 8080, answer `/health`
200 with no I/O, and answer `/ready` 200 with `database: up`. The dependency
layer is about 99 MB uncompressed and `app/` about 1.9 MB, both identical across
the nine, which is what keeps nine repositories close to the storage cost of
one.

`scripts/build_image.sh <domain>` and `scripts/run_image.sh <domain>` are the
local helpers. The first exists so the CodeArtifact token reaches pip as a
BuildKit secret rather than a build argument, where it would persist in
`docker history`; the second runs an image with the environment its entrypoint
needs and points it at `docker-compose.yml`'s DynamoDB Local. `arm64` is the
default platform in both, which is open question 7 and still wants confirming;
the three native pins that question names, `Pillow`, `bcrypt` and `webauthn`,
all publish `aarch64` wheels, and the base image is Debian trixie, whose glibc
satisfies the `manylinux_2_28` floor Pillow's wheel carries.

**Row 12 is delivered.** `.github/workflows/deploy-backend.yml` is a new file
rather than an edit to `backend-deploy.yml`, and that is the one place this
differs from what section 4 sketched. Section 4 describes replacing
`backend-deploy.yml`'s build half while leaving its zip chain intact; splitting
the two into separate files is how that is done, because the monolith
`carmodpicker-<env>-api` is still the only function any route reaches and an
image build that fails must not be able to hold back or roll back the deploy
that serves requests. Two files cannot share a `needs` edge even by accident,
which one file with two independent chains can grow later. `backend-deploy.yml`
is untouched by this PR; section 6.5 is what deletes it.

The chain is `resolve-env`, `build-images`, `image-map`, `existing-functions`,
`deploy-images`, `smoke-domains`. Section 4 named five jobs and there are six:
`existing-functions` is the addition, and it is what makes the deploy half safe
to leave switched on for the whole migration rather than toggled by hand nine
times. Portfolio never needed it, because its Terraform created all four of its
functions before its deploy gate was first turned on, so its deploy was either
wholly off or wholly on. Here row 13 creates `media` alone and rows 18 through 31
add the other eight one at a time, so for most of this migration the truthful
state is that some of the nine exist. A map naming a function that does not exist
fails `aws lambda wait function-updated-v2` with `ResourceNotFoundException` and
takes the whole deploy job red, including the domains that would have succeeded.
So the map is filtered with `get-function-configuration` before it is handed
over, and only a genuine `ResourceNotFoundException` is read as absence: any
other error fails the job, because treating a denied call or an expired
credential as "not created yet" would deploy nothing and report success.

Both halves are gated by repository variables that are absent today, so this PR
changes no behaviour on merge: `BACKEND_IMAGE_BUILD_ENABLED` turns on the build
and `BACKEND_IMAGE_DEPLOY_ENABLED` turns on the deploy, and an unset variable is
the empty string that neither `if` matches. CarModPicker has no
`STAGING_DEPLOY_ENABLED` variable, unlike Portfolio, so the build gate is the
only gate on a staging push. `workflow_dispatch` is present because the workflow
triggers on push and never on a pull request, which makes a merge the earliest
point any of this can run; the first build of the nine images is meant to be
started and watched deliberately rather than discovered in a merge's logs.

The reusable workflow calls are pinned to `@v1.2.1` exactly rather than to the
moving `v1` tag, so the behaviour of this file cannot change without a commit to
it. `build-images` passes `DOMAIN` as its only build argument: unlike Portfolio's
caller there is no `READINESS_PROTOCOL`, because row 11 confirmed all nine poll
`/health` over HTTP and the Dockerfile takes no argument for it. The deploy role
was checked against the four grants this needs, and PR #327 had already added all
of them: ECR push and `BatchGetImage` on the nine `carmodpicker-staging/<domain>`
repositories, ECR pull on `webbpulse/python-lambda-base` in the Artifacts
account, CodeArtifact read with `sts:GetServiceBearerToken`, and
`lambda:InvokeFunction` plus `GetFunctionConfiguration` on all nine. Nothing was
missing, so no Terraform change rides along with this PR and its expected plan
stays zero.

What this PR cannot prove is the build itself. The workflow does not run on pull
requests, and row 11 built all nine images by hand rather than in CI, so the
first push to `staging` with the build gate on is the first time the Dockerfile
is built by Actions: the first exercise of the CodeArtifact token as a BuildKit
secret, of the cross-account base image pull, and of `arm64` on a GitHub runner,
which is open question 7. The PR body carries the checklist for that run.

**Row 13 is delivered.** `terraform/lambda_domains.tf` creates
`carmodpicker-staging-media` from the bootstrap tag, with its execution role,
its runtime policy and its log group, and nothing routes to it. `local.lambda_domains`
is a map with one entry, and the module call, the IAM policy and the three new
outputs all key off it, so rows 18 through 31 each add a map entry rather than a
file.

The list of nine in `ecr.tf` is now `local.lambda_domain_names` and the map is
`local.lambda_domains`, and they are deliberately different objects rather than
one widened in place. All nine repositories exist from row 9 and the deploy role
grants on all nine names from row 10, so those two consumers want the full list
whether or not a function exists; the map wants only what has been created,
because it is what the module iterates and what the outputs report. Keeping them
separate is what lets `deploy-backend.yml`'s `existing-functions` job be
truthful: it filters the image map by what `get-function-configuration` finds,
and from this row until row 31 the honest answer is "some of the nine".

`media`'s two table lists were derived from the code, not from section 1.2's
ownership column, and the two agree. `app/composition/domains.py` declares
`_MEDIA_REPOSITORIES` as five names, `app/db/dynamo/registry.py`'s `tables_for`
maps each to a table suffix, and for `media` that mapping is the identity: five
repositories, five tables. Of the five, `app/api/endpoints/images.py` writes only
`image_source_mappings`, through `.record`; the other four are reached through
`.get` and through `app/api/utils/bucket_orphan_utils.py`'s orphan sweep, which
reads `parts`, `users`, `car_generations` and `build_lists` in full to find
unreferenced S3 objects. Section 1.2 gives `image_source_mappings` to `media` and
names no other writer, and `media` appears in no other row's "also written today
by" column, so `media` is the one domain whose write set needs no seam unwound
before it is cut. That is the other half of why it goes first, alongside Pillow
on `aarch64`.

`rate-limits` is in the write list and is in neither of those places, and the
reason is worth recording because it recurs for all nine. The shared limiter is
middleware, not a repository, so `_MEDIA_REPOSITORIES` cannot name it and
`tables_for` cannot find it; but `add_shared_middleware` puts it in every
application both roots build, so every domain function counts into
`<prefix>-rate-limits` on every request. The limiter fails open, which is exactly
what makes omitting the grant the dangerous choice: the function would keep
serving, layer 2 would be silently off for that domain, and the only symptom
would be a warning per request carrying the structured `rate_limit_failed_open:
true` JSON field. The comment already
in `locals.tf` predicted this and it held.

Section 3.4 lists five S3 actions for `media` and the policy grants four, and
that is a correction rather than a reduction. `s3:HeadObject` is not an IAM
action. It is absent from AWS's machine readable service reference for S3, which
lists 180 actions and none containing "head", and the HeadObject API is
authorized by `s3:GetObject`, which is granted. The same is true of
`s3:HeadBucket`, which `ListBucket` authorizes. IAM accepts an action name that
matches nothing without an error, so the monolith's `user_images_rw` document in
`lambda.tf` carries both today and neither has ever granted anything; only
Access Analyzer's advisory `ValidatePolicy` flags them and nothing in the
pipeline runs it. Copying them into a per-domain policy would make it read
broader than it is, which is the opposite of the point. Section 3.4 should be
read as four actions plus `ListBucket`, and the monolith's two dead actions are
worth dropping in the same pass that retires it.

Two things are deliberately not here. There is no X-Ray statement in the runtime
policy beyond what the module attaches, because `attach_xray_write_policy` covers
`PutTraceSegments` and `PutTelemetryRecords` and the OTLP endpoint's `xray:PutSpans`
belongs with the code that calls it, which is row 16. And no `OTEL_` environment
variable is set, for the same reason: configuring an exporter nothing reads is a
value that looks live and is not.

The environment is the monolith's minus four keys rather than a copy of it, and
one of those four would have been fatal. `PORT` is baked into the image at 8080
alongside `AWS_LWA_PORT`, and the monolith's map sets `PORT=8000`; copying it
wholesale would have bound uvicorn to 8000 while the adapter polled 8080, which
presents as a readiness check that never passes with no application logs to say
why. `RUN_STARTUP_TASKS=false` is baked for the same reason and is not repeated.
`EMAIL_FROM` and `EMAIL_ENABLED` are dropped because `media` sends no mail and
section 3.4 gives SES to `identity` and `admin` only; a configured sender on
a function with no `ses:SendEmail` grant is a configuration that lies.
`SENTRY_SERVICE_NAME` becomes `lambda-media` rather than the monolith's
`lambda-api`, so two functions' events cannot merge into one service in the
window before row 16 removes Sentry from this domain.

`bootstrap_image_tag` is a workspace variable on `CarModPicker-staging` only, at
`sha-ef2e455df9e14ac7251ee1b13331603ff7a90234`, the tag row 11 pushed into all
nine staging repositories. Production has no value for it and needs one, pointing
at a tag in the production account's own repositories, before a per-domain
function is planned there; the variable has no default, so a production plan
fails loudly rather than creating a function from a tag that does not resolve.

**Row 14 is delivered, and it is the first cut.** `terraform/apigateway.tf` gives
the `media` function an integration and two explicit route keys, `ANY /api/images`
and `ANY /api/images/{proxy+}`, so those eight routes now resolve to
`carmodpicker-<env>-media` and everything else still falls through to `$default`
and the monolith. `default_integration = "legacy"` is unchanged and the
monolith's own integration and invoke permission are untouched, which is what
makes the rollback in section 6.4 a matter of deleting one list entry.

The plan is 4 adds rather than the 3 the table predicted, and the missing one is
the invoke permission. A route needs three resources, not two: the integration,
the route, and an `aws_lambda_permission` letting API Gateway call the function.
The module creates the permission per integration rather than per route, so the
count is one integration, two routes and one permission. The estimate counted the
two routes and the integration and forgot that the new function has no
resource-based policy yet, because row 13 created it unrouted. Every later cut
carries the same shape: one integration, one permission, and two route keys per
path prefix, so row 18's `build-logs` is 4 and row 19's `moderation`, with three
prefixes, is 8.

Both route keys per prefix are required, and neither may end in a slash.
`ANY /api/images` does not match `/api/images/upload` and `ANY /api/images/{proxy+}`
does not match the bare collection path, so creating only one of the pair sends
half the domain to the new function and half to the monolith, which section 3.5
calls the worst failure mode because it half works. The trailing slash is a
separate trap and it fails at apply time rather than at plan time: API Gateway
normalises `ANY /api/images/` to the bare key and then rejects the pair as a
duplicate, so a plan that looks green fails the apply.

The routes are data rather than literals. `local.routed_lambda_domains` names the
domains that have been cut and `local.lambda_domain_path_prefixes` names each
one's prefixes from section 1.1's "path prefixes served" column; the integrations
map and the two route keys per prefix are both generated from those. So rows 18
through 31 each add one name and one prefix list, and a domain cannot be left
with an integration nothing routes to, which the module's
`every_integration_is_routed` check would fail the plan on anyway, nor with one
half of a route pair, which nothing would catch.

No `authorization_type` is set on either key, which is deliberate and is the
security-relevant part of this row. The module's own choice is CUSTOM whenever
`authorizer_id` is set, so on staging both new keys carry the access gate's
authorizer exactly as `$default` does. Setting `NONE` on a route to make a probe
convenient would punch a hole straight past the gate for the whole `/api/images`
prefix, and `scripts/verify_route_cut.sh` checks for exactly that by making one
request with no credential and requiring a 401 or 403.

`scripts/verify_route_cut.sh <env> <domain>` is the verification section 6.3
describes, and it reads the access log's `routeKey` rather than a response
header. Portfolio's equivalent script reads an `X-WebbPulse-Domain` response
header that its middleware stamps on every response; CarModPicker's backend sets
no such header, and adding one is a backend change rather than a routing one, so
the access log is the primary signal here rather than the cross-check it is in
Portfolio. That is also why the deploy role gains one narrow grant in this row:
`logs:FilterLogEvents`, scoped to `/aws/apigateway/carmodpicker-<env>-api` and to
that one action. Adding the header later would be worth it, since it is
synchronous and needs no CloudWatch read; the script prefers it if it appears.

Staging is behind the access gate, so a plain `curl` gets a 401 from the
authorizer rather than an answer from the API, which would read as a failed cut
when it is really a missing credential. The script takes
`CARMODPICKER_ORIGIN_VERIFY` (the header value in
`/carmodpicker-staging/access-gate/origin-verify`, which the deploy role could
already read) or `CARMODPICKER_GATE_COOKIE`. With neither it falls back to
invoking the function directly with a synthesised HTTP API v2 event, the same
probe `smoke-domains` uses, and says plainly that this proves the function serves
the paths and not that the gateway routes to them.

The `verify-route-cuts` job in `.github/workflows/deploy-backend.yml` is the
scheduled caller, appended after `smoke-domains` and touching none of the image
build or deploy jobs. A failure there is a routing problem and rolls nothing
back, which is right: the rollback for a bad cut is a Terraform apply, not an
image revert.

**Row 16 is delivered, and it turned tracing on in all nine rather than in one.**
The row was written as `media` only, because when it was written `media` was the
only function that existed. Rows 18 through 31 each say "function, routes, OTel",
and doing the OTel third of each of those eight rows here costs nothing: the
wiring is per domain in shape but identical in content, and
`local.lambda_domain_environment` and the runtime policy in
`terraform/lambda_domains.tf` are both `for_each` over `local.lambda_domains`, so
a domain added in a later row gets the two OTEL_ variables and the `xray:PutSpans`
grant by existing. What those later rows still owe is their function and their
routes, which is the part that actually differs between them. The Terraform plan
is 1 change, as the row predicted, because `media` is still the only entry in the
map.

Three things had to move. `backend/requirements.txt` and
`backend/requirements-lambda.txt` gained the `aws-otel` extra, which carries the
SigV4 signing exporter. `terraform/lambda_domains.tf` sets
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` to this region's X-Ray OTLP endpoint and
`WEBBPULSE_OTEL_SAMPLE_RATIO` to 1.0 on staging and 0.1 on production, and adds
`xray:PutSpans` and `xray:PutSpansForIndexing` to each domain's runtime policy.
And `init_sentry` is gone from all nine entrypoints, leaving Sentry running in
`app/composition/app.py` alone, which is the monolith that still serves
production until row 31.

**The ordering bug this row found is the part worth reading.** Row 8 wired
`configure_tracing` into `build_domain_app` and gated it, and the gate worked, so
nothing looked wrong. But every entrypoint carries a module-level
`app = build_app()` for Mangum, and that line runs at *import*, which is before
`main` has called anything. `build_domain_app` only attaches the FastAPI
instrumentation when a provider already exists, so the module-level application
was built with tracing off and could never be instrumented, and `main` then served
that same object. Setting the environment variable alone would therefore have
produced a function that configured a real tracer provider, exported nothing, and
logged nothing about it. `main` now builds its own application after
`configure_tracing`, and the module-level one stays exactly as it was for Mangum.
This is the failure the package's own docstring warns about from the other
direction: `instrument_app` can only inject its server span middleware while the
middleware stack is unbuilt, so an application that has started cannot be
instrumented after the fact, and the symptom either way is silence.

`backend/tests/entrypoints/test_otel_wiring.py` is what stops it recurring. It
parses each entrypoint rather than reading it as text, so the prose in these
modules can go on explaining why Sentry is absent, and it asserts four things per
domain: no Sentry import and no `init_sentry` call, `configure_logging` before
`configure_tracing`, `configure_tracing` before `build_app`, and that the object
handed to `run_uvicorn` is a fresh `build_app()` call rather than the module
global. The last two are the ones that were actually broken. It also asserts that
the monolith's composition root still calls `init_sentry`, because "Sentry is
removed" is per file here rather than repository wide, and that both requirements
files carry `aws-otel`: the package warns and falls back to the unsigned exporter
when it is missing rather than failing a cold start, so leaving it out of the file
the image installs would produce a function that starts, serves, and silently
exports into a 403.

Two premises the row was written on turned out not to hold, and both are recorded
because the later rows inherit them. The extra is named `aws-otel`, and
`requirements.txt` already predicted that correctly. But `SENTRY_SERVICE_NAME` and
`SENTRY_RELEASE` were still being set on the domain functions, and they are
removed here rather than left as configuration nothing reads; the monolith in
`terraform/lambda.tf` keeps both. And nothing in this row needed a change to
`webbpulse` itself: 0.3.0 already carries the tail sampler, the signing exporter
selection and the per-request flush, so the row is a configuration change and a
call-ordering fix rather than a package adoption.

One thing the split plan should record about section 3.6 and open question 1: the
alarm ceiling has already been lifted upstream. `platform-modules` 2.2.0 removed
the `lambda_function_names <= 10` validation and chunks the list into groups of
ten instead, adding a second alarm pair per group, with no plan change for a
consumer at ten or fewer names. That does not decide open question 1, because the
tradeoff the question describes is unchanged: a chunked alarm still means "group A
is erroring" rather than "the backend is erroring", and `lambda_aggregate_threshold`
still applies within a group. But it does mean the ceiling is no longer a hard
stop that a tenth function runs into, so the decision can be made on the strength
of the signal rather than under a constraint.

**Row 15 is delivered, and open question 1 is answered: the monolith is out of
the list.** `terraform/monitoring.tf` moves the shared `api-alarms` module from
the one function form to the many function form. `lambda_function_name` is
replaced by `lambda_function_names` with `lambda_aggregate_alarm = true` and
`lambda_aggregate_threshold = 0`, so `carmodpicker-<env>-lambda-errors-aggregate`
and `carmodpicker-<env>-lambda-throttles-aggregate` sum AWS/Lambda Errors and
Throttles across the domain functions. The module version stays at `~> 2.4` and
`rate_limit_fail_open_alarm` stays on; neither was touched. Nine domains is under
the module's chunk size of ten, so this is one alarm pair for the whole estate
for the life of the migration and no chunking ever happens.

The two inputs are mutually exclusive by the module's own validation, so
excluding the monolith is not a matter of leaving it out of a list: it destroys
the monolith's own `-lambda-errors` and `-lambda-throttles` alarms. Keeping them
was not free. Adding the monolith to the aggregate would spend a slot on a
function rows 18 through 31 are retiring and would make "the backend is erroring"
mean "the backend or the thing it is being moved off is erroring", which is the
signal the whole aggregate shape exists to protect. The module's
`lambda_errors_alarm_function_name` escape hatch is the other route and is worse:
it creates an alarm named `<prefix>-lambda-errors`, which is exactly the alarm
this change destroys, so it would buy the errors half back as a no-op that hides
the decision instead of recording it.

The monolith is not uncovered meanwhile. It still serves every route not yet cut,
so an invocation failure in it is a gateway 5xx and `<prefix>-api-5xx` fires on
that, including for the init failures and timeouts that never reach the gateway
as an application response and are the only things AWS/Lambda Errors would have
caught that the 5xx alarm would not. Its log group stays in `error_log_groups`,
so its ERROR records still reach `<prefix>-application-errors`, and its limiter
still reaches `<prefix>-rate-limit-failed-open`. Row 31 removes the monolith and
the rest of its coverage together.

Both lists are derived rather than written out, so rows 18 through 31 extend the
alarms by adding a domain rather than by editing this file.
`lambda_function_names` filters `local.lambda_domain_names` from `ecr.tf` down to
the domains whose function actually exists, and the filter rather than the map is
the load-bearing part. The module turns the list into positional metric math ids
`m0`, `m1` and so on, so a reorder rewrites both alarm definitions; reading
`keys()` off `local.lambda_domains`, which is what Portfolio does, returns
Terraform's lexicographic key order rather than the insertion order, so on
CarModPicker's cut order it would yield `catalog, identity, media` where the plan
wants `media, identity, catalog` and would reshuffle every id on any mid-alphabet
insert. Portfolio can afford it because all four of its domains landed at once;
here they arrive one row at a time, which is precisely when the difference bites.
Filtering section 6.1's ordered list gets append-only growth for free.

The plan is 3 to add, 1 to change and 2 to destroy, against the table's estimate
of 6 change, and both halves of the estimate were wrong in an instructive way. It
assumed all nine functions existed by this row, when row 13 created `media` alone
and the other eight are still rows 18 through 31, so the aggregate covers one
function today and grows to nine. And it assumed the switch was an in-place edit
of an existing alarm pair, when the two input forms produce differently named
resources: `-lambda-errors` and `-lambda-throttles` are destroyed and
`-lambda-errors-aggregate` and `-lambda-throttles-aggregate` are created. The
third add is the `media` error metric filter, which is `error_log_groups` growing
to cover the domain functions and not only the monolith, and the one change is
that alarm's description tracking the count, from "1 log group" to "2 log
groups". That last one is worth noting for later rows: every cut from 18 onward
will show one metric filter add plus that same one-line description change, so a
plan of two rather than one there is expected rather than a surprise.

The log-based half is the half that scales, and this row is where it starts
carrying the estate. Every filter writes the same dimensionless metric, so
`<prefix>-application-errors` stays exactly one alarm however many log groups it
grows to and has no metric math ceiling to run into, which is what section 3.6
recommended before the ceiling was lifted upstream and is still the right shape
now that it has been.

**Row 18 is delivered, and it is the second cut.** `build-logs` gets a function,
a route pair and its OTel wiring, and every one of those three arrives by adding
a name to a list rather than by writing a resource. `local.lambda_domains` in
`terraform/lambda_domains.tf` gains a `build-logs` entry, which creates the
function, its role and its runtime policy; `local.routed_lambda_domains` and
`local.lambda_domain_path_prefixes` in `terraform/apigateway.tf` gain the name
and the one prefix, which creates the integration, the invoke permission and the
two route keys; and the alarm lists in `terraform/monitoring.tf` pick the domain
up for free, because both are derived rather than written out. Nothing in
`backend/` changed at all, which is the part worth stating plainly: rows 8 and 16
had already built and instrumented all nine entrypoints, so the OTel third of
this row was done before the row was reached, and `app/entrypoints/build_logs.py`
is byte for byte what row 16 left. `backend/tests/entrypoints/test_otel_wiring.py`
needed no extension for the same reason: it parametrises over `DOMAIN_NAMES`, so
it has been asserting the four wiring properties on this entrypoint since row 16.

One prefix, `/api/build-logs`, and both keys of its pair. All five of the
domain's routes sit under it: `GET /api/build-logs/posts/count`,
`GET /api/build-logs/build-list/{build_list_id}`,
`POST /api/build-logs/build-list/{build_list_id}/posts`, and the `PUT` and
`DELETE` on `/api/build-logs/posts/{post_id}`. None of the five is the bare
collection path, and `ANY /api/build-logs` is still created, because the pair is
what section 3.5 requires and half a pair is the failure mode that half works.
`/api/build-logs` and `/api/build-lists` are distinct route keys and API Gateway
matches literally, so this cut cannot pull any of `build-lists`' 34 routes with
it; those stay on `$default` until row 26.

The table split is the one judgement call in the row, and it is narrower than the
ownership column would suggest. Section 1.2 gives `build-logs` ownership of both
`build_logs` and `build_log_posts`, but only `build_log_posts` is in `tables`.
The domain's five routes call `.create`, `.update` and `.delete` on
`repos.build_log_posts` and nothing else; `build_logs` is reached only through
`.get` and `.for_build_list`, both reads. The writes to `build_logs` are real but
they are somewhere else: `app/api/services/build_list_service.py` creates the
thread when a build list is created, and `build_log_delete_actions` in
`app/db/dynamo/build_logs.py` deletes it in the build list cascade, and both run
in `build-lists`. Ownership says who may write a table, not who does today, so
granting this function write on a table no code path here writes would be an
action nobody takes, which is what a per-domain split exists to stop. Row 26
moves that seam and the grant follows the writer then. `users` and `build_lists`
are ordinary cross-domain reads, and `rate-limits` is in `tables` for the reason
`media`'s entry records: the limiter is reached from the middleware rather than
from a repository, and it fails open, so withholding it would turn layer 2 off
silently instead of failing.

Memory is 256 MB against `media`'s 512. `media` is sized for Pillow decoding an
uploaded image in memory; this domain serves five JSON routes over DynamoDB with
no native work in the path, so it starts at the smaller size, which is also the
cheapest thing to raise if the duration says otherwise.

The speculative plan is 11 to add, 4 to change and 0 to destroy, against the
table's estimate of 6 add, and the whole of the gap is resources the estimate did
not know it was buying rather than anything unexpected in the row. Four of them
are the alarms, which row 15's own delivery note predicted for exactly this row.

The eleven adds, grouped by what put them there:

*The function, four resources rather than one.* `module.lambda_domain["build-logs"].aws_lambda_function.this`,
`module.lambda_domain["build-logs"].aws_iam_role.this`,
`module.lambda_domain["build-logs"].aws_cloudwatch_log_group.this` and
`module.lambda_domain["build-logs"].aws_iam_role_policy.xray_write[0]`, plus
`aws_iam_role_policy.lambda_domain["build-logs"]`, the runtime policy this
repository writes rather than the module. Row 13 recorded its own count as 3 for
the same shape, which was the module's function, role and runtime policy; the log
group and the X-Ray policy are the module's too, and they were not counted then
either. Five is the real per-function number and rows 19 through 31 should be
estimated on it.

*The routes, four resources, exactly as row 14 found.*
`module.api.aws_apigatewayv2_integration.this["build-logs"]`,
`module.api.aws_lambda_permission.this["build-logs"]`, and the pair
`module.api.aws_apigatewayv2_route.this["ANY /api/build-logs"]` and
`module.api.aws_apigatewayv2_route.this["ANY /api/build-logs/{proxy+}"]`. One
integration, one permission and two keys per prefix is the shape row 14 wrote
down, and a one-prefix domain lands on it exactly.

*The alarms, two adds and four changes, and none of it was in the table.*
`module.alarms.aws_cloudwatch_log_metric_filter.errors["build-logs"]` and
`module.alarms.aws_cloudwatch_log_metric_filter.rate_limit_failed_open["build-logs"]`
are the new function's log group joining the two log-based alarms. The four
changes are the two description strings tracking the count, "2 log groups" to
"3 log groups" on `module.alarms.aws_cloudwatch_metric_alarm.errors[0]` and on
`module.alarms.aws_cloudwatch_metric_alarm.rate_limit_failed_open[0]`, and the
two aggregate alarms
`module.alarms.aws_cloudwatch_metric_alarm.lambda_aggregate_errors[0]` and
`module.alarms.aws_cloudwatch_metric_alarm.lambda_aggregate_throttles[0]`, whose
descriptions move from "1 function" to "2 functions" and whose metric math grows
a term. Row 15 predicted the metric filter and the description change and called
a plan of two rather than one there expected; what it did not say is that
`rate_limit_fail_open_log_groups` is a second list of the same shape, so a cut
adds two filters and moves two descriptions, not one of each.

The aggregate metric math is the part worth reading, because it is the first
evidence that row 15's ordering argument holds. `m0` stays
`carmodpicker-staging-media` and `build-logs` arrives as `m1`, and the expression
goes from `m0` to `m0 + m1`. That is an append rather than a rewrite, which is
what filtering section 6.1's ordered `local.lambda_domain_names` was for: reading
`keys()` off the map instead would have put `build-logs` before `media`
lexicographically and renumbered the existing term. Rows 19 through 31 can expect
the same append, and a plan that shows `m0` changing its label is the signal that
something reordered the list.

Nothing is destroyed and nothing on `media` or on the monolith moves, which is
the property that makes this row's rollback deleting a list entry again.

`scripts/verify_route_cut.sh` gains `/api/build-logs` in its `build-logs` case,
which was already present and empty so the script would fail loudly rather than
pass on an empty loop, and the `verify-route-cuts` job in
`.github/workflows/deploy-backend.yml` gains the name in its one-line `DOMAINS`
list. The `build-images` matrix needed nothing: it has carried all nine domains
since row 12, because building an image for a function that does not exist yet
costs an ECR push and no behaviour. Two comments in the verify script that read
"most of `media`'s routes require a token" are now written domain neutrally,
since a second domain runs through the same probe and the statement is true of
both.


**Ingestion is now admin.** Open question 4 asked whether the domain should be
renamed and the answer is yes, taken on 2026-09-07. Section 1.5 had already
argued the case: `crawled_pages` writes nothing, the listing writes the old name
implies live in `catalog`, and what is actually in the domain is the price alerts
plus `admin/db_ops` and `admin/stats`. The name now says what the twenty
repositories in its bundle already said.

The question predicted this would be cheap now and expensive after the first cut,
and the shape of the change bears that out. Nothing about the API moved: no
route, no URL path, no prefix, no tag, no OpenAPI operation id. The route
contract fixture and the published OpenAPI document are byte-identical, which is
what makes the change reviewable as a rename rather than as a refactor. What did
move is the deployment-unit name in eleven files: the descriptor and its
repository tuple in `app/composition/domains.py`, the entrypoint module
`app/entrypoints/ingestion.py` to `admin.py`, the valid-domain `case` list in
`backend/Dockerfile` and in both `scripts/build_image.sh` and
`scripts/run_image.sh`, the build matrix in `.github/workflows/deploy-backend.yml`,
`local.lambda_domain_names` in `terraform/ecr.tf`, the two per-domain test
expectations in `backend/tests/entrypoints/`, and the prose here and in
`CLAUDE.md`. `service_name` derives from the descriptor's `name`, so
`lambda-ingestion` became `lambda-admin` with no edit of its own, and
`terraform/iam_github_actions.tf` derives the nine function ARNs from
`local.lambda_domain_names`, so it changed without being touched.

The one cost is in ECR. Renaming the repository is a destroy and a create, not a
rename, and `carmodpicker-staging/ingestion` holds the three images row 11 pushed
by hand. `force_delete` is a destroy-time flag that the provider reads from prior
state rather than from configuration, and a key removed from a `for_each` map has
no configuration left to evaluate, so it cannot be switched on in the same apply
that removes the key. The images are disposable, nothing has ever deployed from
them, and emptying the repository first is a smaller change than two applies with
the guardrail left off; `terraform/ecr.tf` carries the command. Production owns
none of these repositories yet, so it pays nothing at all.

Had this waited until after row 21, the name would additionally have been in a
live Lambda function, its log group, its execution role and inline policy, its
alarm dimensions, and the image tags of everything already deployed, and the
rename would have meant recreating a function that was serving traffic. That is
the difference the open question was pointing at.

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

**1. The alarm ceiling. Answered: the monolith is out of the list, and done.**
Taken on 2026-09-08 and delivered by row 15. `lambda_function_names` carries the
nine domains and not the monolith, so the nine share one aggregate errors alarm
and one aggregate throttles alarm, nine is under the module's chunk size of ten,
and no chunking happens. The signal stays "the backend is erroring" rather than
"group A is erroring", which is what the question was really protecting. The cost
is that the monolith's own `-lambda-errors` and `-lambda-throttles` alarms are
destroyed rather than kept, because the module's two input forms are mutually
exclusive; until row 31 retires it, its invocation failures surface through
`<prefix>-api-5xx` and its logged errors through `<prefix>-application-errors`.
Section 3.6's paragraph on row 15 has the full reasoning.

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

**4. Renaming `ingestion`. Answered: yes, and done.** It held price alerts and
two admin modules, and `crawled_pages` touches no repository, so `admin`
describes it better. Renamed on 2026-09-07, before its function existed. Section
8's "Ingestion is now admin" paragraph records what it cost.

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
for storage across nine log groups. Confirm it is wanted. **Answered by row 17,
which is delivered:** 7 days everywhere, and the two groups the question was
really about were the monolith's, not the nine. The nine domain functions were
created on 7 from the start, in row 13, and `aws/spans` was imported on 7, so the
only groups still carrying the old value were the ones the pre-migration stack
built. The speculative plan is 0 add, 2 change, 0 destroy, matching the estimate,
and `retention_in_days` is the only attribute that moves on either resource:
`module.lambda_api.aws_cloudwatch_log_group.this`
(`/aws/lambda/carmodpicker-staging-api`) and
`module.api.aws_cloudwatch_log_group.access`
(`/aws/apigateway/carmodpicker-staging-api`), both 14 to 7. Retention is a
property of the group rather than of the events in it, so the apply reprices the
existing backlog as well: anything already older than 7 days ages out on the next
sweep instead of at 14. The monolith is the function still serving every route
that has not been cut, so this is the window that shrinks in practice, and it
shrinks while the cuts in rows 18 through 31 are still landing.

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
