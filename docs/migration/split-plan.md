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
item and returns. A Lambda event source mapping on the `users` stream sees the
tombstone and fans the work out onto the `user-delete` work queue, one message per
unit of cleanup, and each domain drains what it owns and deletes its own rows with
its own IAM. One queue rather than one per subscribing domain: the fan out is a
message shape, not a queue per consumer, and eleven queues to say the same thing
is eleven redrive policies and eleven alarms to maintain. The tombstone is the
contract: `users` owns it, and every domain that reads a user must treat a
tombstoned user as absent.

The consequence is what makes this hard rather than tedious. Between the
tombstone write and the last queue draining, the application is in a half-deleted
state, and every read path that joins to a user has to tolerate it. Concretely,
`build-lists`, `build-logs`, `moderation`, and `vehicles` all read `users` to
attach an author, and all four must filter tombstoned users out rather than
rendering a blank author. That filtering has to land **before** `users` is cut,
not with it.

Row 23 delivered that filtering and found the four-domain list wrong; its
delivery note in section 8 has the corrected surface, which is `build-logs` and
`moderation` plus `search`, not `build-lists` and `vehicles`.

**Open item for row 30: when are the uniqueness reservations released?** The
hard delete does it in the same transaction as the row delete.
`UserRepository.delete_user` is a `transact_write` of three actions, the item
delete plus `release_unique_action` on `USERNAME` and on `EMAIL`, so the moment a
user is gone the username and email are reusable. A tombstone has no such moment.
Hold the reservations until the queue drains and a user who deletes their account
cannot re-register with their own address for as long as the cleanup takes;
release them with the tombstone write and there is a window in which a live
reservation points at an id whose row still exists and still reads as a user to
anything that has not been taught the predicate. The tombstone write and the
release are also no longer one transaction, so a partial failure leaves the pair
inconsistent in whichever direction is chosen. This has to be decided in row 30
rather than discovered in it. The same question applies to `oauth_accounts`,
whose `delete_link` releases `PROVIDER_ACCOUNT` and `USER_PROVIDER` the same way.

**Seam 2: the part purge.** `part_service.purge_related_rows_for_parts` deletes a
part and then writes into `build_list_parts`, `votes`, `reports`, and
`part_price_alerts`, owned by `build-lists`, `moderation` twice, and `admin`.
Same mechanism, smaller blast radius: a tombstone on `parts` plus a stream, and a
mapping that fans the cleanup onto the `part-purge` work queue for `build-lists`,
`moderation`, and `admin` to drain.

The read-path consequence is real here too and is more visible to users than the
user cascade. A build list that contains a purged part must not render a hole; it
must drop the row. So `build-lists` gains a tombstone check on the part join
before `catalog` is cut. Row 23 delivered that check, and found the join
wider than this paragraph implies: the cost sum in `build_lists.py` prices parts
too, and a purged part must not be priced into a total any more than it should be
rendered as a row.

**Open item for row 28: the part purge releases two things a tombstone does
not.** Both are in the synchronous path today and neither has an owner once the
delete becomes a tombstone write.

- **The uniqueness reservations on `parts`.** `PartService.purge` ends in
  `repos.parts.delete_unique`, which releases the `gtin` reservation and the
  `manufacturer + part_number` reservation alongside the row. Tombstone the part
  and those reservations outlive it, so a genuinely new part carrying the same
  GTIN as a purged one is rejected as a duplicate of a row no user can see. It is
  the same question as seam 1's username and email and should be answered the same
  way, but the blast radius is different: a blocked GTIN is a catalog data problem
  rather than an account problem, and it fails closed rather than open.
- **The S3 objects behind `image_urls`.** A purged part's images are handled by
  `bucket_orphan_utils.py` rather than by the purge itself, which sweeps for
  objects no row references. A tombstoned part still has a row and still
  references its objects, so the sweep will not collect them and the storage is
  held for as long as the tombstone is. Whether the tombstone should clear
  `image_urls` at write time, or the sweep should learn the predicate, is a
  decision for row 28. Open question 6 already notes the sweep is a full-table
  scan behind an HTTP route and will time out as the tables grow, so the two are
  worth deciding together.

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
`NEW_AND_OLD_IMAGES`. Streams are not configured on any table today, and
`dynamodb_tables.json` carries no stream field, so the view type is set per table
in `terraform/dynamodb.tf` through `local.dynamodb_stream_view_types`. Enabling a
stream is an in-place `UpdateTable` and never replaces a table. The view type is
the part to get right first: it cannot be edited once a stream exists, so changing
it later mints a new stream ARN and silently detaches every consumer reading the
old one.

**A stream is read by a Lambda, not by a queue.** The earlier draft of this plan
had each stream feeding one SQS queue per subscribing domain. There is no such
path. An event source mapping targets a Lambda function and nothing else, and
DynamoDB Streams has no native delivery to SQS, so those queues would have had
nothing writing to them. The pattern the seams actually use is an event source
mapping directly on the stream, with the batch size and window set per consumer,
`bisect_batch_on_function_error`, `maximum_retry_attempts`,
`function_response_types = ["ReportBatchItemFailures"]` so a partial batch failure
retries only the records that failed, and an `on_failure` destination pointing at
an SQS dead letter queue.

Those mappings and their consumer functions arrive with the seams that need them,
rows 24 and 25, so **row 22 creates no event source mappings and no consumer
Lambdas**. What it does create is the four dead letter queues the mappings will
name, one per streamed table, because a destination that does not exist is an
apply time failure rather than a plan time one. Note what an `on_failure` record
holds: metadata about the failed batch and the shard position it came from, not
the stream records themselves. A responder draining one of these re-reads the
stream at that position, which only works inside the stream's own 24 hour
retention.

**SQS work queues are for the asynchronous jobs only**, not for stream fan out.
Two of them, `part-purge` for seam 2 in row 28 and `user-delete` for seam 1 in
row 30, each with its own dead letter queue and a redrive policy with
`maxReceiveCount` 5. A cleanup handler that fails repeatedly must not silently
drop a delete, because the visible symptom is a user who deleted their account and
whose build lists are still public.

Six queues in total, all standard rather than FIFO, all with SSE-SQS on. The
visibility timeout on the two work queues is six times the intended consumer
timeout, which is assumed to be the same 29 seconds every domain function uses;
that assumption is written down in `terraform/sqs.tf` because the timeout has to
move if a consumer is ever given a longer one. Dead letter queue depth is one
aggregate alarm over all six queues using metric math, never one alarm per
queue.

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
| 20 | `vehicles`: function, routes, OTel. **Delivered** | medium | 13 add, 4 change | 19 |
| 21 | `admin`: function, routes, OTel. **Delivered** | medium | 17 add, 4 change | 20 |
| 22 | Streams on `users`, `parts`, `votes`, `part_listings`, plus the six queues and the DLQ alarm. **Delivered** | large | 4 change, 9 add (recorded 16 add at the time, before the queue count was settled) | 21 |
| 23 | Tombstone attributes and tombstone-aware reads. **Delivered** | large | 0 | 22 |
| 24 | Seam 3: `net_votes` handler moves to `catalog`'s stream consumer, on an event source mapping. **Delivered** | medium | 6 add, 3 change (est. 3 add) | 22 |
| 25 | Seam 4: price alert email moves to an `admin` stream handler, on an event source mapping | medium | est. 3 add | 22 |
| 26 | `build-lists`: function, routes, OTel | large | est. 17 add, 4 change | 23 |
| 27 | `identity`: function, routes, OTel | medium | est. 11 add, 4 change | 23 |
| 28 | Seam 2: part purge goes async | large | 2 add | 23 |
| 29 | `catalog`: function, routes, OTel | large | est. 17 add, 4 change | 28 |
| 30 | Seam 1: user delete cascade goes async | large | 5 add | 23, 29 |
| 31 | `users`: function, routes, OTel. **Ninth cut, alarm list full** | large | est. 13 add, 4 change | 30 |
| 32 | Retire `$default`, the monolith, the artifacts bucket, the zip chain | medium | 12 destroy | 31 |
| 33 | Frontend: delete the `services/Api.ts` shim, rewriting 74 import sites | medium | 0 | none |

**Rows 26 through 31 are estimates, and the arithmetic behind them is worth
stating rather than hiding. Rows 19, 20 and 21 landed on it exactly, so it is
settled rather than provisional.** Row 18's delivery note found the per-cut shape by
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
and `users` 2, which is where the numbers in the table come from. Rows 19, 20 and
21 have each now counted a real plan and found exactly 15, 13 and 17 adds with 4
changes, so the remaining rows are arithmetic rather than guesswork. Each row's
delivery note should still record what it actually saw. The seam and stream rows (22, 24, 25, 28, 30) are not
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


**Row 19 is delivered, and it is the third cut.** `moderation` gets a function,
three route pairs and its OTel wiring, and like row 18 every one of those arrives
by adding a name to a list. `local.lambda_domains` in
`terraform/lambda_domains.tf` gains the entry;
`local.routed_lambda_domains` and `local.lambda_domain_path_prefixes` in
`terraform/apigateway.tf` gain the name and its three prefixes; and the alarm
lists in `terraform/monitoring.tf` pick the domain up for free. Nothing in
`backend/` changed, for the reason row 18 records: rows 8 and 16 had already
built and instrumented all nine entrypoints, so `app/entrypoints/moderation.py`
is byte for byte what row 16 left, `app/composition/domains.py` already declares
the descriptor and its three routers, and `test_otel_wiring.py` parametrises over
`DOMAIN_NAMES`. The routes the composition serves are exactly the three prefixes
this row cuts.

**The plan is 15 to add, 4 to change and 0 to destroy, and the estimate was
right.** Row 18's per-cut anatomy predicted `5 + 2 + 2*prefixes + 2` adds and 4
changes, which for a three-prefix domain is 15 and 4. This is the first row to
land on the corrected arithmetic rather than to discover it, so the anatomy holds
and rows 20 through 31 can be estimated on it with some confidence.

The fifteen adds, in the anatomy's own groups:

*The function, five resources.*
`module.lambda_domain["moderation"].aws_lambda_function.this`,
`module.lambda_domain["moderation"].aws_iam_role.this`,
`module.lambda_domain["moderation"].aws_cloudwatch_log_group.this`,
`module.lambda_domain["moderation"].aws_iam_role_policy.xray_write[0]` and
`aws_iam_role_policy.lambda_domain["moderation"]`, the runtime policy this
repository writes rather than the module.

*The integration, two resources.*
`module.api.aws_apigatewayv2_integration.this["moderation"]` and
`module.api.aws_lambda_permission.this["moderation"]`, one of each regardless of
how many prefixes the domain serves, which is what this row confirms: three
prefixes still buy exactly one integration and one permission.

*The routes, six resources, two per prefix.*
`ANY /api/votes`, `ANY /api/votes/{proxy+}`, `ANY /api/reports`,
`ANY /api/reports/{proxy+}`, `ANY /api/bug-reports` and
`ANY /api/bug-reports/{proxy+}`, all as
`module.api.aws_apigatewayv2_route.this[...]`. The bare keys carry more weight
here than they did for `build-logs`, where none of the five routes was the
collection path. All three of these collection paths are real routes the domain
serves, so omitting a bare key would have left the collection on the monolith
while everything below it moved, which is the half-working failure section 3.5
names.

*The alarms, two adds and four changes, exactly as row 18 saw.*
`module.alarms.aws_cloudwatch_log_metric_filter.errors["moderation"]` and
`module.alarms.aws_cloudwatch_log_metric_filter.rate_limit_failed_open["moderation"]`
are the new log group joining the two log-based alarms. The four changes are the
two description strings, "3 log groups" to "4 log groups" on
`module.alarms.aws_cloudwatch_metric_alarm.errors[0]` and on
`module.alarms.aws_cloudwatch_metric_alarm.rate_limit_failed_open[0]`, and the
two aggregate alarms
`module.alarms.aws_cloudwatch_metric_alarm.lambda_aggregate_errors[0]` and
`module.alarms.aws_cloudwatch_metric_alarm.lambda_aggregate_throttles[0]`, whose
descriptions move from "2 functions" to "3 functions".

The metric math is the second confirmation of row 15's ordering argument and the
first with three terms. `m0` stays `carmodpicker-staging-media`, `m1` stays
`carmodpicker-staging-build-logs`, `moderation` arrives as `m2`, and the
expression goes from `m0 + m1` to `m0 + m1 + m2`. An append again, with no
existing term relabelled, which is what filtering the ordered
`local.lambda_domain_names` buys. Reading `keys()` off the map would have sorted
`build-logs`, `media`, `moderation` and left `media` at `m1`.

**The table split is this row's judgement call, and unlike row 18's it is wider
than the ownership column rather than narrower.** Four tables are written:
`votes`, `reports` and `bug_reports`, which are the domain's own and which
`vote_service`, `report_service` and `bug_report_service` each write through
`.create`, `.update` and `.delete`; and `parts`, which is not.

`parts` is seam 3. `vote_service._sync_part_net_votes` calls
`self.repos.parts.update(str(entity_id), net_votes=upvotes - downvotes)` after
every vote create, update and remove whose entity type is a part, and section 1.3
already names it as the one cross-domain write in the application that is not a
delete. Row 24 inverts it into a stream handler `catalog` owns, and the grant
narrows to a read then. Until then it is a real write on a live path, and
withholding the grant would break voting on a part rather than tightening
anything. The failure would also be an unpleasant one to debug: the sync runs
after the vote row is committed, so an AccessDenied would leave the vote written
and `net_votes` stale behind a 500 on a request that half succeeded. The grant
follows the writer, which is the same rule row 18 applied to reach the opposite
answer on `build_logs`.

Three tables are read only. `users` for the reporter and the author, through
`repos.users.get` and `.get_many` in `report_service`, and `build_lists` and
`car_generations` for the vote and report targets. Those targets are the reason
this domain has three prefixes and only nine repositories: votes and reports are
polymorphic over an `entity_type`, and `_get_entities` dispatches to
`repos.build_lists.get_many`, `repos.car_generations.get_many` or
`repos.parts.get_many` accordingly. `parts` is in `tables` rather than
`read_tables` because a table belongs to exactly one of the two lists and the
twelve write actions are a superset of the five read ones.

`car_makes` and `car_models` are in `_MODERATION_REPOSITORIES` and get no grant
at all, which is the first time a bundle and a grant list have differed for a
reason other than read against write. The bundle test computes reachability
through the import graph, and those two arrive with the catalogue types the vote
and report schemas name; no route, service or utility in the domain calls
`repos.car_makes` or `repos.car_models`. Granting a table on the strength of an
import rather than a call would hand the function two tables no request can
reach. Later rows should expect the same gap wherever a schema pulls in a type
from a domain the code does not otherwise touch.

Memory is 256 MB, the same as `build-logs`. Twenty JSON routes over DynamoDB,
with no Pillow, no image decoding and no native work in any of the three endpoint
modules or their three services.

`scripts/verify_route_cut.sh` gains the three prefixes in its `moderation` case,
which was present and empty so the script failed loudly rather than passing on an
empty loop, and the `verify-route-cuts` job in
`.github/workflows/deploy-backend.yml` gains the name in its one-line `DOMAINS`
list. The `bootstrap_image_tag` gate from row 13's follow-up needed nothing from
this row, which is the property it was built for: both new list entries are
filtered through `local.lambda_domains`, so an account with no images resolves
the function and the routes to empty together and neither the entry nor the
prefixes have to know the gate exists.


**Row 20 is delivered, and it is the fourth cut and the one the least-privilege
claim rests on.** `vehicles` gets a function, two route pairs and its OTel
wiring, and as with rows 18 and 19 every one of those arrives by adding a name to
a list. `local.lambda_domains` in `terraform/lambda_domains.tf` gains the entry;
`local.routed_lambda_domains` and `local.lambda_domain_path_prefixes` in
`terraform/apigateway.tf` gain the name and its two prefixes; and the alarm lists
in `terraform/monitoring.tf` pick the domain up for free. Nothing in `backend/`
changed, for the reason rows 18 and 19 record: rows 8 and 16 had already built
and instrumented all nine entrypoints, so `app/entrypoints/vehicles.py` is byte
for byte what row 16 left.

**The plan is 13 to add, 4 to change and 0 to destroy, and the estimate was right
for the second row running.** Row 18's per-cut anatomy predicts
`5 + 2 + 2*prefixes + 2` adds and 4 changes, which for a two-prefix domain is 13
and 4. Two rows have now landed on that arithmetic rather than discovering it, so
it can be treated as settled.

The thirteen adds, in the anatomy's own groups: five for the function
(`aws_lambda_function.this`, `aws_iam_role.this`, `aws_cloudwatch_log_group.this`
and `aws_iam_role_policy.xray_write[0]` inside
`module.lambda_domain["vehicles"]`, plus `aws_iam_role_policy.lambda_domain["vehicles"]`);
two for the integration (`module.api.aws_apigatewayv2_integration.this["vehicles"]`
and `module.api.aws_lambda_permission.this["vehicles"]`); four routes, two per
prefix (`ANY /api/car-generations`, `ANY /api/car-generations/{proxy+}`,
`ANY /api/search` and `ANY /api/search/{proxy+}`); and two metric filters,
`errors["vehicles"]` and `rate_limit_failed_open["vehicles"]`. The four changes
are the two description strings moving from "4 log groups" to "5 log groups" and
the two aggregate alarms moving from "3 functions" to "4 functions".

The metric math is the third confirmation of row 15's ordering argument. `m0`
stays `media`, `m1` stays `build-logs`, `m2` stays `moderation`, `vehicles`
arrives as `m3`, and the expression goes from `m0 + m1 + m2` to
`m0 + m1 + m2 + m3` with no existing term relabelled. That is what filtering the
ordered `local.lambda_domain_names` buys; reading `keys()` off the map would have
sorted `build-logs`, `media`, `moderation`, `vehicles` and moved `media` to `m1`.

**`/api/search` is the reason this domain has two prefixes rather than one, and
the bare key matters more here than anywhere so far.** `/api/search` has no path
below it at all: the domain is a single `GET` on the collection itself. Omitting
its bare route key would have left the only route of the prefix on the monolith
while its `{proxy+}` key matched nothing, which is section 3.5's half-working
split in its purest form. `/api/car-generations/search` is a separate matter and
needs no key of its own; it is matched by `ANY /api/car-generations/{proxy+}`, and
because API Gateway matches a route key literally rather than by substring the
two search paths do not collide and no ordering between them is implied.

**The table split is this row's real content, and it is the first entry whose
write list holds no table the domain owns.** Seven tables are read and one is
written, and the one written is `rate-limits`, the shared limiter's counter,
which every domain carries because the middleware writes it on every non-exempt
request and fails open when it cannot. Nothing else is written at all.

Both routers are read only by construction. `car_generations.py` builds its
`BaseDynamoEndpointRouter` with `disable_endpoints = ["create", "update",
"delete"]`, so the generated writing routes are never registered and the seven
hand-written routes above it are all `GET`; `search.py` is one `GET`. Neither
`car_generation_service.py` nor the `search_parts` path calls `.create`,
`.update` or `.delete` on any repository.

The seed is the one write this domain owns, and it does not run in this function.
`vehicles` is the only descriptor setting `seeds`, and `run_startup_tasks` is
gated on `settings.RUN_STARTUP_TASKS`, which `backend/Dockerfile` bakes to
`false` and which `local.lambda_domain_environment` deliberately does not set.
The entrypoint is Mangum with `lifespan="off"` besides, so the lifespan that
would call `init_car_generations()` never runs under Lambda. Section 7 already
says the seed needs an owner and belongs behind an explicit admin route or a
one-off job, and `admin/db_ops` has the equivalent endpoint, so the write grant
that covers it lands with row 21 rather than here. Granting the three car tables
write to cover a seed that cannot fire would have given away the least-privilege
claim for nothing.

**The gap between the bundle and the grants is wider here than on any cut so
far, and for a new reason.** `_VEHICLES_REPOSITORIES` is
`_CATALOG_REPOSITORIES + ("build_lists",)`, sixteen repositories, and seven are
granted. Rows 18 and 19 saw a gap of one or two tables arriving through schema
imports; this one is nine, and the cause is a single line. `search.py`
constructs a `PartService`, so the whole of that module's import graph is
reachable, while the only method any route calls on it is `search_parts`. The
nine ungranted repositories, `categories`, `retailers`, `part_cars`,
`part_listings`, `part_price_history`, `part_price_alerts`, `build_list_parts`,
`votes` and `reports`, are reached only from `PartService` methods no vehicles
route calls, chiefly the part purge and the price capture, several of which are
writes. Granting on the strength of an import would have handed a read-only
function nine tables no request can touch, four of them with write paths.

The seven granted reads are the three car tables and seam 5's four. The car
tables are called rather than merely imported: `car_generations.py` calls
`repos.car_makes.count()` and `repos.car_models.count()` directly, and
`car_generation_service._models_and_makes` calls `get_many` on both on every
hydrate. The other four are the search fan-out section 1.3 leaves synchronous:
`build_lists` and `users` scanned from `search.py`, and `parts` and
`part_manufacturers` from `search_parts`. Cross-domain reads are allowed with
read-only IAM, and reads are the whole of what this domain does.

**`secrets` is false, and this is the only one of the nine entries where it
is.** Section 3.4 calls `vehicles` the cheapest proof that the IAM split is real,
and this row is where that is paid out: every route under both prefixes is a
public read, `allow_public_read = true` keeps `get_current_user` off the
generated routes, and the descriptor sets no `requires_secrets`, so nothing in
the function reads `SECRET_KEY`. The runtime policy carries no
`secretsmanager:GetSecretValue` statement and the environment carries no
`APP_SECRETS_ARN`. This is only possible because section 2.3's lazy secret
resolution landed first: while importing `app.core.config` still called Secrets
Manager, every function needed the grant whether it used a secret or not.

Memory is 256 MB, the same as `build-logs` and `moderation`. Eleven read-only
JSON routes with no Pillow and no native work. Search is the one route worth a
second thought, since `scan_matching` pages full table scans of `build_lists`,
`users` and `parts` and holds the matches in memory, but it is bounded by
`DYNAMODB_SEARCH_SCAN_PAGE_LIMIT` and holds parsed models rather than decoded
images. Memory is the cheapest knob to raise if the duration says otherwise.

`scripts/verify_route_cut.sh` gains the two prefixes in its `vehicles` case,
which was present and empty, and the `verify-route-cuts` job in
`.github/workflows/deploy-backend.yml` gains the name in its `DOMAINS` list.
`terraform/README.md` is brought current in the same pass: its `lambda_domains.tf`
row had still said two entries since row 18, and its `apigateway.tf` row had
never mentioned the route cuts at all.

**Row 21 is delivered, and it is the fifth cut and the mirror image of the
fourth.** `admin` gets a function, four route pairs and its OTel wiring, and as
with rows 18 through 20 every one of those arrives by adding a name to a list.
`local.lambda_domains` in `terraform/lambda_domains.tf` gains the entry;
`local.routed_lambda_domains` and `local.lambda_domain_path_prefixes` in
`terraform/apigateway.tf` gain the name and its four prefixes; and the alarm
lists in `terraform/monitoring.tf` pick the domain up for free. Nothing in
`backend/` changed, for the reason the three rows before it record: rows 8 and 16
had already built and instrumented all nine entrypoints, so
`app/entrypoints/admin.py` is byte for byte what row 16 left.

**The plan is 17 to add, 4 to change and 0 to destroy, and the estimate was right
for the third row running.** Row 18's per-cut anatomy predicts
`5 + 2 + 2*prefixes + 2` adds and 4 changes, which for a four-prefix domain is 17
and 4. The arithmetic can now be treated as settled rather than as a working
hypothesis, and rows 26 through 31 should be planned against it.

The seventeen adds, in the anatomy's own groups: five for the function
(`aws_lambda_function.this`, `aws_iam_role.this`, `aws_cloudwatch_log_group.this`
and `aws_iam_role_policy.xray_write[0]` inside `module.lambda_domain["admin"]`,
plus `aws_iam_role_policy.lambda_domain["admin"]`); two for the integration
(`module.api.aws_apigatewayv2_integration.this["admin"]` and
`module.api.aws_lambda_permission.this["admin"]`); eight routes, two per prefix
(`ANY /api/crawled-pages`, `ANY /api/part-price-alerts`, `ANY /api/admin/db-ops`
and `ANY /api/admin/stats`, each with its `{proxy+}`); and two metric filters,
`errors["admin"]` and `rate_limit_failed_open["admin"]`. The four changes are the
two description strings moving from "5 log groups" to "6 log groups" and the two
aggregate alarms moving from "4 functions" to "5 functions". Zero destroys and
zero replacements.

The metric math is the fourth confirmation of row 15's ordering argument. `m0`
stays `media`, `m1` stays `build-logs`, `m2` stays `moderation`, `m3` stays
`vehicles`, `admin` arrives as `m4`, and the expression goes from
`m0 + m1 + m2 + m3` to `m0 + m1 + m2 + m3 + m4` with no existing term relabelled.

**`/api/admin/db-ops` and `/api/admin/stats` are section 1.4's one genuine
cross-domain ordering hazard, and this row resolves it rather than documenting
it.** There is no route at `/api/admin` itself, so the two children are named as
two prefixes rather than collapsed into one. Collapsing them would be wrong
twice: it would claim `/api/admin/{anything}` for this function forever, and
section 1.4's warning that no other domain may take a child of `/api/admin`
without accounting for it would become impossible to honour.
`/api/users/admin/users` is a separate tree and is unaffected, because API
Gateway matches a route key literally rather than by substring.

The `/api/part-price-alerts` bare key is the one carrying real traffic rather
than sitting there defensively. `part_price_alerts.py` declares subscribe as
`POST "/"`, which mounts at `/api/part-price-alerts/`, and the gateway normalises
the trailing slash onto the bare key; a route key may not itself end in a slash,
so the bare key is the only spelling the gateway will accept for that route. The
other three prefixes have every route below them, so their bare keys are the
cheap insurance section 3.5 asks for.

The module ordering inside `/api/part-price-alerts` is untouched and stays that
way by not touching the module. `/unsubscribe` is registered before the two
`/{alert_id}` routes and section 1.4 calls that the one hazard a route away from
breaking silently; the `{proxy+}` key forwards the whole subtree to one function,
exactly as it forwards to the monolith today, so nothing about the cut can
reorder it. Splitting the subtree across route keys is what would break it, and
nothing here does.

**The table split is this row's real content, and it is the exact opposite of row
20's.** Fourteen tables are written plus the limiter's counter, and six are read.
That is the widest write list of the nine, where `vehicles` had the narrowest,
and both are the same rule applied honestly: the grant follows the call. The two
admin modules seed and purge six domains' tables by design, and section 1.5
already argued that one broad admin function is better than pushing those writes
behind the six functions that own the tables.

Every written table has a named caller. `part_price_alerts` is the domain's own,
per section 1.2, written by `part_price_alert_service` from subscribe, patch,
delete and the token unsubscribe, and by `purge_related_rows_for_parts`. The
other thirteen are `admin/db_ops`, which is four routes:
`POST /admin/db-ops/init/car-generations` runs `init_car_generations`, which
calls `.create_unique` and `.update_unique` on `car_makes`, `car_models` and
`car_generations`; `POST /admin/db-ops/init/part-categories` runs
`init_part_categories` on `categories`; `POST /admin/db-ops/cars/delete-all`
calls `.update` on `build_lists` to null `car_id`, `.delete_for_entity_type` on
`votes`, `.delete_for_car` on `part_cars` and `.delete_unique` on the three car
tables; and the two delete-all routes run the part purge, which reaches
`part_listings`, `part_price_history`, `parts`, `part_cars`, `votes`, `reports`,
`build_list_parts`, `part_price_alerts` and `part_manufacturers`.

**The seed row 20 deliberately did not grant lands here, which is what that row
said would happen.** `vehicles` is the descriptor that sets `seeds`,
`run_startup_tasks` is gated on `RUN_STARTUP_TASKS`, which `backend/Dockerfile`
bakes to `false`, and the entrypoint is Mangum with `lifespan="off"`, so the
lifespan that would call `init_car_generations()` cannot run there. Here it is an
explicit `POST` behind `get_current_admin_user`, which is exactly the owner
section 7 said the seed needed. The write grant follows the route rather than the
table's owner, and the three car tables are in this entry's `tables` list for
that reason.

**The bundle-to-grant gap is one table, the narrowest of the five cuts so far.**
`_ADMIN_REPOSITORIES` is twenty-one, the second widest bundle after the
monolith's twenty-five, and twenty are granted. The one left out is `retailers`,
and neither of its two reaches is an admin route:
`part_price_alert_service.evaluate_alerts_for_listing` calls `repos.retailers.get`
for the email body and is invoked only from
`part_listing_service.create_or_update_listing_and_price`, which is `catalog`'s
price capture; and `PartService`'s create and update paths call it, while the
only `PartService` method any admin route calls is `purge`. Rows 19 and 20
refused to grant on the strength of an import and this row refuses the same way,
which is the only thing that keeps a write list this wide honest.

The six read-only tables are `users`, read before eleven of the twelve handlers
run because `get_current_user` and `get_current_admin_user` both call
`repos.users.get_by_username` to resolve the token subject, and the five that
`admin/stats` counts and nothing writes: `oauth_accounts`,
`webauthn_credentials`, `build_list_phases`, `build_logs` and
`image_source_mappings`. `part_listings`, `part_price_history`, `part_cars`,
`votes` and `reports` are counted by that route as well and are in `tables`
rather than in `read_tables`, because a table appears in exactly one of the two
lists and the twelve write actions include the five read ones.

**`secrets` is back to true, and `admin` gets no SES.** Eleven of twelve routes
verify a token and the twelfth, the price-alert unsubscribe, decodes one of its
own, so the descriptor sets `requires_secrets` and the runtime policy carries
`secretsmanager:GetSecretValue`. Section 3.4 also gives `admin` `ses:SendEmail`,
and this row does not, because `admin`'s half of that grant is the price-drop
alert email and no route this function serves sends it: the send is in
`evaluate_alerts_for_listing`, called from `catalog`'s price capture, which runs
on the monolith today. A send grant and an `EMAIL_FROM` here would be
configuration for a code path that cannot execute, which is the same argument
`lambda_domains.tf`'s header already makes about the monolith's environment map.
Row 25 is seam 4, and the grant and the environment key arrive there with the
handler that uses them. `s3` is false for the same kind of reason: `crawled_pages`
parses HTML from the request body and touches no bucket, and the `crawl-data`
bucket is read by nothing in this domain.

Memory is 256 MB, the same as the three cuts before it. Twelve JSON routes over
DynamoDB with no Pillow and no native work. The delete-all routes are the ones
worth a second thought, because `repos.parts.list_all()` and
`repos.build_lists.scan_all()` hold whole tables in memory, but the binding
constraint there is the 29 second timeout rather than the memory: open question 6
already says a full-table admin operation behind an HTTP route will time out as
the tables grow, and a job rather than a larger function is the answer to that.

`scripts/verify_route_cut.sh` gains the four prefixes in its `admin` case, which
was present and empty, and the `verify-route-cuts` job in
`.github/workflows/deploy-backend.yml` gains the name in its `DOMAINS` list. The
script's direct-invoke fallback gains a comment recording a false negative it has
had since row 18: it probes the bare prefix with a `GET` and treats a 404 as a
failure, and `/api/build-logs`, `/api/reports`, `/api/votes`,
`/api/admin/db-ops` and `/api/admin/stats` all have every route below the prefix,
so a working function genuinely answers 404 there. CI never takes that path,
because `verify-route-cuts` supplies `CARMODPICKER_ORIGIN_VERIFY` on staging and
needs no gate credential on production, and the gateway path accepts any answer
that is not a 5xx and reads the route key out of the access log.

**Set `bootstrap_image_tag` before confirming a row-cut apply, and confirm the
image exists.** Row 20's apply failed on `CreateFunction` because the workspace
variable still pointed at row 14's commit and `ecr.tf`'s keep-last-10 rule had
expired that image out of the `vehicles` repository; refreshing the variable to
the staging head and re-applying fixed it. A speculative plan cannot catch this,
because the plan renders the image URI as a string and only `CreateFunction`
resolves it, so the run is green and the apply fails partway through. Every row
cut is exposed to it, because a cut creates a function from that tag in a
repository no function has ever been created from. The routine, added to
`terraform/README.md`'s `bootstrap_image_tag` entry in the same pass: set the
variable to `sha-<current staging head>`, confirm the tag is present with
`aws ecr describe-images --repository-name carmodpicker-<env>/<domain> --image-ids imageTag=sha-<sha>`,
then confirm the apply.

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

**Row 23 is delivered, and the row's own description of it was wrong.** The
plan said "`build-lists`, `build-logs`, `moderation`, and `vehicles` all read
`users` to attach an author, and all four must filter tombstoned users out". Two
of those four read no users at all. `build-lists` joins to `parts`, not to
`users`; `vehicles` has no user concept anywhere in `car_generations`. The
four-domain framing was a guess at the shape of the join graph rather than a
reading of it, and the real surface is both narrower on users and wider on parts
than the row implied. Corrected, the read sites are:

- **`build-lists` joins to `parts`, not to `users`.** Two `get_many` hops in
  `get_parts_in_build_list` (`app/api/endpoints/build_list_parts.py`), the stored
  parts and the canonical parts a duplicate resolves to, plus `_require_part` on
  the add and update routes, plus the cost sum in `app/api/endpoints/build_lists.py`
  that would otherwise price a purged part into a build list total.
- **`build-logs` is the one domain that genuinely attaches an author.** Both its
  sites, the batch join in `get_build_log_by_build_list` and the single get on
  the create path, funnel through `_post_with_author`, so the filter is one line
  there rather than two at the call sites.
- **`moderation` reads both users and parts, at eight sites.**
  `report_service.py` has four: the reporter and the reviewer in the batch list,
  the same pair in `get_report_by_id`, and the part in `_get_entity_or_404` and
  `_get_entity_details`. `bug_report_service.py` has three, the `username()`
  closure and both single gets. `vote_service.py` has one, `_get_entities`, which
  is the chokepoint both the vote route and the flagged-entity listing share.
- **`catalog` filters its own reads,** which the row did not mention at all but
  which is where a tombstoned part would otherwise be most visible: `_matches` in
  `PartService` (every `candidates()` branch ends there), `page_by_category`,
  `list_page_read`, `search_parts`, a `get_by_id` override because the route is
  generated by `BaseDynamoEndpointRouter`, and `_get_part_or_404` in
  `app/api/endpoints/parts.py` for the listing, image and price-history routes.
- **`search.py` covers both users and parts** through
  `UserRepository.search`, which is the one path that filters server-side.

**The predicate is one function, not a repository concern.** It lives in
`app/db/dynamo/tombstones.py` beside the models that carry the attributes. The
obvious home, a filter inside `DynamoRepository` applied to every read, does not
work: the widest join in the application goes through `CatalogRepository.get_many`,
which is a `BatchGetItem`, and that API takes no filter expression. So the
predicate is applied in Python after the batch get everywhere a batch get is
involved, and as a `filter_expression` only on `UserRepository.search`, which is
a scan and where it keeps behaviour identical. Hiding it in the repository layer
would have silently missed the one path that matters most.

**This row adds the attributes and the reads, and deliberately not the writes.**
`deleted` and `deleted_at` are on the `User` and `Part` models and nothing sets
them. Both deletes are still hard deletes that cascade synchronously inside the
request: `_delete_user_everywhere` in `app/api/endpoints/users.py` and
`PartService.purge` plus `purge_related_rows_for_parts`. Flipping either write
here would strand rows across eleven tables, because the stream consumers that
drain the cascade off a work queue do not exist until rows 28 and 30 and row 22
created the queues without any event source mapping. The predicate is therefore
live ahead of its producer on purpose: every row reads as not deleted today, and
the read paths stay correct the moment a tombstone first appears.

**Expected plan: 0, and it held.** No Terraform changed. `deleted` and
`deleted_at` are non-key attributes, DynamoDB is schemaless for those, and
`terraform/dynamodb_tables.json` carries only key attributes, secondary indexes
and the TTL field. No GSI is needed either: nothing queries by tombstone, every
read that filters had already reached its rows by another index. Existing rows
lack both attributes and read as live, so there is no backfill.

No response schema changed. `UserRead`, `PublicUserRead` and `PartRead` are
explicit field allowlists rather than model dumps, so the two attributes cannot
leak into a public response, and the OpenAPI snapshot and the extension contract
tests both pass untouched. They are internal attributes and should stay that way.

Twenty-five tests were added: eight on the predicate itself
(`tests/db/test_dynamo_tombstones.py`), thirteen on the read paths
(`tests/api/endpoints/test_tombstone_aware_reads.py`), and four pinning what the
two synchronous cascades currently remove
(`tests/api/endpoints/test_delete_cascades.py`). That last file exists because
neither cascade had a test, which is a bad position from which to make one
asynchronous: rows 28 and 30 are correct only if they end in the same state, and
nothing recorded what that state was. The read tests include a regression test
for the hard-delete drop in `get_parts_in_build_list`, which was the behaviour
the tombstone filter had to preserve and which was untested.

**Row 24 is delivered, and it is the first row that runs code off a stream.**
Seam 3 is inverted. `vote_service._sync_part_net_votes` is gone, the vote path
writes only `votes`, and `carmodpicker-<env>-catalog-votes-consumer` recomputes
`parts.net_votes` from the `votes` stream that row 22 turned on. `moderation`'s
`parts` grant moved from `tables` to `read_tables` in the same commit, which is
the narrowing every row from 19 onward has been promising.

**The two halves have to land in one apply, and they do.** Removing the grant
before the consumer exists leaves the aggregate with nothing writing it; adding
the consumer before removing the grant leaves two writers racing on the same
attribute. Both are in `terraform/`, so the only way to separate them is to split
the commit, which is why the commit is not split. There is no backfill and no
cutover window either: the synchronous write and the consumer compute the
identical number, `upvotes - downvotes`, so the column is correct on both sides
of the apply and the mapping starts at `LATEST` rather than replaying a day of
records to recompute values that are already right.

**Recount, never increment.** The handler reads the vote count for a part and
writes the difference; it does not adjust `net_votes` by the delta a record
implies. This is the whole idempotency argument. A DynamoDB stream is
at-least-once and is ordered only within a partition key, which here is the vote
id, so records for one part arrive from many shards with no order between them
and any record may be delivered twice. An increment would drift on every
redelivery and could not be repaired without a full rebuild. A recount converges:
replaying a batch, or the whole day, produces the same number. The handler also
skips the write when the recomputed value equals the stored one, which keeps a
replay from writing at all.

**A stream consumer is still a web application here, and that is the adapter's
documented shape.** This is the part worth reading carefully, because the obvious
guess is wrong. The base image is `python:3.13-slim` with the Lambda Web Adapter
copied into `/opt/extensions/lambda-adapter`. There is no `awslambdaric` in it
and no ENTRYPOINT, so there is no runtime interface client to resolve a handler
string like `module.handler`: pointing `image_config.command` at one would make
Lambda exec a file of that literal name and the container would not start. The
adapter *is* the runtime. It polls the Runtime API itself and forwards each
invoke to a local web server, and for a trigger that is not HTTP it POSTs the raw
event JSON to `AWS_LWA_PASS_THROUGH_PATH`, default `/events`, and returns the
app's response body as the function result. The adapter documents DynamoDB
streams among the non-HTTP triggers this covers.

So `app/entrypoints/catalog_votes_consumer.py` is a FastAPI app like its nine
neighbours. It serves `GET /health`, the readiness path the Dockerfile already
sets, and `POST /events`, which reads the stream event off the request body,
calls `app.consumers.votes.handle`, and answers `{"batchItemFailures": [...]}`.
Terraform starts it with `image_config.command = ["python", "-m",
"app.entrypoints.catalog_votes_consumer"]`, the same `python -m` form the image's
own CMD uses, and sets `AWS_LWA_PASS_THROUGH_PATH = "/events"` explicitly so the
contract is visible in a plan rather than resting on a default.

**It also sets `AWS_LWA_ERROR_STATUS_CODES = "500-599"`, and without that the
error path silently does not work.** That variable is opt-in: by default the
adapter hands a 500 response back to Lambda as a *successful* invoke. An
unhandled exception in the consumer would then look like a clean run, the mapping
would ack the batch, and the records would be gone. With it set, the 500 that
FastAPI's error handling produces surfaces as a real function error, which is
what makes the mapping bisect, retry, and eventually route the batch to the
stream dead letter queue. The entrypoint deliberately does not catch and convert
unexpected exceptions into an empty failure list for the same reason.

**It is a separate function rather than a route on `catalog`.** Since the
consumer is a web app, a `/events` route on the existing `catalog` function would
technically work. It is still the wrong answer: the mapping's concurrency,
timeout and error rate would be shared with the API, a vote storm would take
request capacity from routes users are waiting on, and a consumer bug would page
as a catalog API error. A second function off the same image keeps what matters
about sharing anyway. It is better than a tenth ECR repository would have been:
one build, one push and one digest means the deploy that updates `catalog`
updates the consumer with identical bytes and the two cannot skew. The platform
module has supported `image_config` since v2.0.1, so the existing `~> 2.1` pin
already covers it. `deploy-backend.yml` gained an `EXTRA_FUNCTIONS` map that
emits the consumer alongside `catalog` from the same manifest.

The consumer does not mount `add_shared_middleware`. CORS is meaningless when the
only caller is the adapter over loopback with no `Origin`, and the shared rate
limiter is worse than meaningless: it writes to `rate-limits`, which this function
has no grant for, so it would fail open on every invoke, log a warning each time,
and trip the `rate-limit-failed-open` alarm on ordinary traffic. It mounts
`request_context_middleware` and the error handlers only.

**Smoking it by hand.** `smoke-domains` skips anything ending in `-consumer`,
which stays correct, though for a narrower reason than the name suggests: the
consumer does answer `GET /health`, it just has no API Gateway route, and that
job reaches a function by invoking it with a synthesised API Gateway v2 payload.
The equivalent probe is a direct invoke with a stream shaped payload, and an
empty batch is enough to prove the container starts, the adapter forwards, and
the app answers:

```
aws lambda invoke --function-name carmodpicker-staging-catalog-votes-consumer \
  --payload '{"Records":[]}' --cli-binary-format raw-in-base64-out /dev/stdout
```

which returns `{"batchItemFailures":[]}`.

**The mapping's settings are all failure handling, because the defaults stall a
shard.** A DynamoDB stream shard is ordered and a failing batch blocks it, and
the default `maximum_retry_attempts` of -1 retries until the record expires, so
one poison record with the defaults stops every later record on that shard for 24
hours. The mapping therefore sets `bisect_batch_on_function_error`,
`maximum_retry_attempts = 2`, `maximum_record_age_in_seconds = 3600`,
`function_response_types = ["ReportBatchItemFailures"]` and an `on_failure`
destination of `carmodpicker-<env>-votes-stream-dlq`, the queue row 22 created for
exactly this. The handler returns `batchItemFailures` naming only the sequence
numbers of the records for the part it could not write, so one unwritable part
does not cause every other part in the batch to be recomputed again. Bisecting is
the backstop for the case the response cannot cover: a timeout or an out-of-memory
kill returns no response at all, so there is no failure list to read and the whole
batch retries.

**Alarms: folded in, no new alarm, and the ceiling is now reached.** Consumer
errors join `lambda_function_names` and its log group joins `error_log_groups`,
so the existing `<prefix>-lambda-errors`, `<prefix>-lambda-throttles` and
`<prefix>-application-errors` alarms cover it with no per-resource alarm added.
The DLQ is already covered: the single `<prefix>-dlq-depth` alarm row 22 created
spans all six queues including this one. The consumer is appended after the nine
domains rather than sorted among them, because the aggregate alarms are metric
math over positional ids and `catalog-votes-consumer` sorts before `media`, so an
alphabetical merge would rewrite every expression on both existing alarms.

That makes ten functions, which is exactly the module's chunk size. **Row 25's
consumer is the eleventh and will chunk into a second alarm pair.** That is worth
deciding rather than discovering: it doubles the alarms to subscribe and splits
"the backend is erroring" across two notifications, which is the outcome open
question 1 was protecting against. Whoever cuts row 25 should choose deliberately
between accepting the second pair and giving the consumers an aggregate of their
own.

**The frontend change is smaller than open question 2 assumed, and better.** See
that question's answer: the frontend never read `net_votes`, so there was no
stale aggregate on screen to fix. What changed instead is that the vote routes
now return the authoritative counts and `VoteButtons.tsx` uses them, which
removes a round trip rather than adding one.

**Expected plan: 6 add, 3 change, 0 destroy.** The adds are the four resources
the `lambda-function` module creates for
`carmodpicker-<env>-catalog-votes-consumer` (`aws_lambda_function`,
`aws_iam_role`, `aws_cloudwatch_log_group`, and the X-Ray write policy), plus its
runtime `aws_iam_role_policy` and the `aws_lambda_event_source_mapping`. The
changes are the two aggregate Lambda alarms gaining a tenth metric and the
GitHub Actions deploy policy gaining the eleventh function ARN; a new metric
filter for the consumer's log group and the `application-errors` alarm's
description are folded into those. **`bootstrap_image_tag` must be refreshed to a
tag that currently resolves in the catalog ECR repository before this is
applied.** It seeds `image_uri` on function creation, Lambda pulls the image at
`CreateFunction`, and the keep-last-10 lifecycle policy expires old tags: the
plan is green either way and the apply is what fails.

The estimate in the table said 3 add. It counted the mapping, the function and
its policy and did not count the three resources the module creates alongside a
function, which is the same undercount row 22's estimate made.

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

**2. `net_votes` eventual consistency. Answered: return the count, and done.**
Taken by row 24, which took the second option. The vote and un-vote routes now
answer with `VoteMutationResult`, the vote plus the entity's `upvotes`,
`downvotes`, `total_votes` and `vote_score` read from the `votes` table in the
same request, and `VoteButtons.tsx` overwrites its optimistic guess with those
numbers. The lag is real but nothing displays it.

The question's own reservation, that this is a frontend change in the middle of
a backend migration, turned out to be smaller than it reads, for a reason the
question could not have known: **the frontend never read `net_votes` at all.** It
renders `upvotes - downvotes` from `VoteSummary`, and `net_votes` is used only
server-side, as the `rating` sort key in `PartService`. So the stale-number
problem the question describes was never going to appear in the UI, and the
change that was worth making was a different one. The old client updated its
counts optimistically and had no authoritative number until something else
re-fetched; it now gets the true count on the write it already makes. That
removes a round trip rather than adding one, and it is a strict improvement
whether or not the aggregate lags.

The response also carries the counts for car generations and build lists, which
have no denormalised aggregate to go stale. One response shape across the three
entity types is worth more than saving a query on two of them, and it keeps the
frontend from branching on which entity it voted for.

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
