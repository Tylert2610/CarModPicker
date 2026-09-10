# The HTTP API: the API itself, the $default stage with throttling and the JSON access log, the
# Lambda proxy integrations and their invoke permissions, the routes, and the custom domain with
# its mapping and alias record. All from the shared platform module.
#
# Section 3.5 and section 6 of docs/migration/split-plan.md: the strangler ran through this file
# and is finished. While it ran, each cut added route keys for one domain and the monolith kept
# everything else through $default, so a cut was one entry in local.routed_lambda_domains plus that
# domain's route keys and a rollback was deleting them again. Row 31 cut the ninth and last domain
# and row 32 removed $default, the "legacy" integration and the monolith behind them, so there is
# no fallthrough left: a path no explicit route key matches is a 404 from the gateway.

locals {
  # Domains that have been cut over, in the order section 6.1 cuts them. A domain belongs here only
  # once local.lambda_domain_route_keys names its route keys: the module's every_integration_is_routed
  # check fails the plan on an integration no route can reach, so the two move together.
  #
  # Row 14 is `media`, row 18 is `build-logs`, row 19 is `moderation`, row 20 is `vehicles`,
  # row 21 is `admin`, row 26 is `build-lists`, row 27 is `identity`, row 29 is `catalog` and
  # row 31 is `users`. That is all nine: every domain in section 1.1 is routed, and row 32 retired
  # the monolith that had been serving the five root routes through `$default`. This list is now
  # the whole API, and `default_integration = null` below is what says so.
  routed_lambda_domains_declared = ["media", "build-logs", "moderation", "vehicles", "admin", "build-lists", "identity", "catalog", "users"]

  # Gated on the same condition as the functions themselves, and it has to be. A route names an
  # integration and an integration names module.lambda_domain[name], so a routed domain whose
  # function was not created is an error at plan time rather than a route that quietly points
  # nowhere. Gating both on local.domain_functions_enabled in lambda_domains.tf is what lets a
  # fresh account apply this root before any image exists, and it is also what keeps the two in
  # step in the other direction: the deploy workflow's verify-route-cuts job hardcodes the domain
  # list and fails on a function that exists without its routes, so the pair must be created in
  # one apply rather than in two.
  #
  # The filter rather than a bare conditional so that a name can only be routed if the domain is
  # also in local.lambda_domains. Today the two lists hold the same names and the filter is a
  # no-op; it is what makes a future row that adds a route entry before the function entry a plan
  # that drops the route rather than one that fails on a missing module key.
  routed_lambda_domains = [
    for name in local.routed_lambda_domains_declared : name
    if contains(keys(local.lambda_domains), name)
  ]

  # The path prefixes each domain serves, from section 1.1's "Path prefixes served" column. Only a
  # routed domain needs an entry; the rest arrive with their own row.
  #
  # Both keys are needed per prefix and section 3.5 says why. "ANY /api/images" does not match
  # /api/images/upload, and "ANY /api/images/{proxy+}" does not match the bare collection path.
  # Omitting the bare route sends the collection endpoint to $default and the detail endpoints to
  # the new function, which is the worst failure mode available because it half works.
  #
  # A route key may not end in a slash: API Gateway normalises "ANY /api/images/" to the bare key
  # and rejects the pair as a duplicate at apply time while the plan stays green. The prefixes here
  # therefore carry no trailing slash and the keys are built from them directly.
  lambda_domain_path_prefixes = {
    media = ["/api/images"]
    # Row 18. One prefix, and all five of this domain's routes sit under it:
    # /api/build-logs/posts/count, /api/build-logs/build-list/{id},
    # /api/build-logs/build-list/{id}/posts, and the two on
    # /api/build-logs/posts/{post_id}. The bare key matches none of those five
    # and is still required, because without it the collection path falls to
    # $default while the rest of the prefix moves, which is the half-working
    # split the comment above describes.
    #
    # `/api/build-logs` and `/api/build-lists` are different prefixes and API
    # Gateway matches a route key literally, so this cut cannot pull any of
    # build-lists' 34 routes with it. Those stay on $default until row 26.
    build-logs = ["/api/build-logs"]
    # Row 19. Three prefixes, the most of any cut so far, because this domain is
    # polymorphic rather than wide: votes and reports are keyed by an
    # `entity_type` and an `entity_id`, so one domain moderates parts, build
    # lists and car generations through three separate route trees. Bug reports
    # are unrelated to the other two and share the domain because they share the
    # shape.
    #
    # Six route keys, a bare and a `{proxy+}` for each. The bare keys are not
    # optional here and matter more than they did for `build-logs`, because all
    # three collection paths are real routes this domain serves: `GET`, `POST`
    # and the admin listings sit directly on `/api/votes`, `/api/reports` and
    # `/api/bug-reports`, so omitting a bare key would leave the collection on
    # the monolith while every path below it moved.
    #
    # `/api/reports` and `/api/bug-reports` are separate route keys and API
    # Gateway matches a key literally rather than by string prefix, so neither
    # shadows the other and no ordering between them is implied. Nothing else
    # in section 1.1 sits under any of the three.
    moderation = ["/api/votes", "/api/reports", "/api/bug-reports"]
    # Row 20. Two prefixes, and they are two rather than one because this domain
    # merges an entity tree with a fan-out: `/api/car-generations` is the three
    # car tables' read surface and `/api/search` is seam 5's unified search,
    # which reads four domains' tables and belongs here only because section 1.5
    # would otherwise leave `vehicles` the smallest domain.
    #
    # Four route keys, a bare and a `{proxy+}` for each. Both bare keys are real
    # routes rather than defensive: `GET /api/car-generations` is the generated
    # list endpoint and `GET /api/search` is the entire search domain, which has
    # no path below it at all. Omitting the `/api/search` bare key would leave
    # the only route of that prefix on the monolith while its `{proxy+}` matched
    # nothing, which is the half-working split section 3.5 names, in its purest
    # form.
    #
    # `/api/car-generations/search` is a real route of this domain and needs no
    # key of its own. It is matched by `ANY /api/car-generations/{proxy+}`, and
    # it does not collide with the `/api/search` prefix: API Gateway matches a
    # route key literally rather than by substring, so the two trees are
    # independent and no ordering between them is implied. Nothing else in
    # section 1.1 sits under either prefix.
    vehicles = ["/api/car-generations", "/api/search"]
    # Row 21. Four prefixes, the most of any cut so far, and two of them are the
    # only place in the whole map where one domain claims two children of a
    # parent it does not itself serve.
    #
    # `/api/crawled-pages` and `/api/part-price-alerts` are ordinary prefixes:
    # one endpoint module each, a bare key for the collection and a `{proxy+}`
    # for everything below.
    #
    # `/api/admin/db-ops` and `/api/admin/stats` are section 1.4's one genuine
    # cross-domain ordering hazard, and this is where it is resolved. There is
    # no route at `/api/admin` itself, so the two children are named explicitly
    # rather than collapsed into a single `/api/admin` prefix. Collapsing them
    # would be wrong twice over: it would claim `/api/admin/{anything}` for this
    # function forever, and section 1.4 warns that no other domain may take a
    # child of `/api/admin` without accounting for it, which a broad key would
    # make impossible to do safely. `/api/users/admin/users` is a separate tree
    # entirely and is unaffected, because a route key matches literally rather
    # than by substring.
    #
    # The `/api/part-price-alerts` bare key matters more than it looks.
    # `part_price_alerts.py` registers `/unsubscribe` before its two
    # `/{alert_id}` routes and section 1.4 calls that the one ordering hazard a
    # route away from breaking silently. That ordering is decided inside the
    # module and is preserved by the `{proxy+}` key forwarding the whole subtree
    # to one function, exactly as it forwards to the monolith today. Splitting
    # the subtree across route keys is what would break it, and nothing here
    # does.
    #
    # Eight route keys, a bare and a `{proxy+}` for each of the four.
    # `/api/part-price-alerts` is the one whose bare key carries real traffic:
    # `part_price_alerts.py` declares the subscribe endpoint as `POST "/"`,
    # which mounts at `/api/part-price-alerts/`, and API Gateway normalises a
    # trailing slash onto the bare key, so `ANY /api/part-price-alerts` is what
    # matches it. A route key may not itself end in a slash, so the bare key is
    # not merely the better spelling here, it is the only one the gateway will
    # accept. The other three prefixes have every route below them
    # (`/scrape`, the four `db-ops` operations and `/table-counts`), so their
    # bare keys are the defensive half section 3.5 asks for: cheap, and the
    # difference between a clean cut and one that half works if a collection
    # route is ever added.
    admin = ["/api/crawled-pages", "/api/part-price-alerts", "/api/admin/db-ops", "/api/admin/stats"]
    # Row 26. Four prefixes and the largest cut so far by route count: 34 routes,
    # against `admin`'s 12 and `moderation`'s 20. The four are four sibling
    # trees rather than one tree with children, which is why they are four
    # prefixes and not one: `/api/build-lists` is the parent in the domain model
    # but not in the URL space, and `/api/build-list-parts`,
    # `/api/build-list-phases` and `/api/build-list-labor-estimates` are
    # siblings of it rather than paths below it.
    #
    # That sibling shape is also what makes the keys safe. API Gateway matches a
    # route key literally rather than by string prefix, so `/api/build-lists`
    # does not claim `/api/build-list-parts` even though one is a character
    # prefix of the other, and neither claims `/api/build-logs`, which row 18
    # already cut and whose own comment above anticipated this row. All five
    # trees are independent keys and no ordering between them is implied.
    #
    # Eight route keys, a bare and a `{proxy+}` for each of the four. Three of
    # the four bare keys are the defensive half section 3.5 asks for, because
    # `build-list-parts`, `build-list-phases` and `build-list-labor-estimates`
    # have every route below the prefix. The `/api/build-lists` bare key is not
    # defensive and carries real traffic, in the same way `/api/part-price-alerts`
    # does for `admin`: `build_lists.py` declares the create endpoint as
    # `POST "/"` and `BaseDynamoEndpointRouter` generates the list endpoint as
    # `GET "/"`, so both mount at `/api/build-lists/`. API Gateway normalises the
    # trailing slash onto the bare key and a route key may not itself end in a
    # slash, so `ANY /api/build-lists` is the only spelling that matches them and
    # writing the literal path with its slash is an apply-time BadRequestException
    # on a plan that was green.
    #
    # Section 1.4's two `build-lists` ordering hazards are both inside a module
    # and are untouched by this map. `/api/build-lists/with-votes`, `/count`,
    # `/car/{id}` and `/user/me` resolve before the generated `{entity_id}`
    # because `build_lists.py` registers them first, and
    # `/api/build-list-parts/parts/{part_id}/build-lists/count` resolves against
    # `/{build_list_id}` on segment count. Both survive because the `{proxy+}`
    # key hands the whole subtree to one function, which leaves FastAPI's
    # registration order deciding exactly as it does on the monolith today.
    # Splitting either subtree across route keys is what would break them, and
    # nothing here does.
    build-lists = ["/api/build-lists", "/api/build-list-parts", "/api/build-list-phases", "/api/build-list-labor-estimates"]
    # Row 27. One prefix, the fewest of any cut, and 24 routes under it: the
    # login and token routes, email verification, password reset, TOTP 2FA,
    # WebAuthn passkeys and Google OAuth. The four endpoint modules mount at
    # `/auth`, `/auth/2fa`, `/auth/webauthn` and `/auth/oauth`, so the three
    # sub-prefixes are paths below this one rather than siblings of it, which is
    # the opposite of row 26's shape and is why one prefix covers the domain.
    #
    # Two route keys, and this is the first cut whose bare key is purely
    # defensive. Walking `app.routes` on the built application puts all 24
    # routes under `ANY /api/auth/{proxy+}` and none on the bare key: there is
    # no route at `/api/auth` and none declared as `"/"`, unlike
    # `/api/build-lists` in row 26 or `/api/part-price-alerts` in row 21, whose
    # bare keys carry real traffic. The key is still required rather than
    # optional, for the reason section 3.5 gives: without it a collection route
    # added at `/api/auth` later would fall to `$default` while everything below
    # it stayed here, which is the half-working split that is worse than either
    # whole. It also costs nothing to carry.
    #
    # The trailing-slash trap does not bite here and is worth saying so
    # explicitly rather than leaving to inference. A route key may not end in a
    # slash, and no route in this domain mounts at `/api/auth/`, so the bare key
    # is written bare because that is the only legal spelling and not because a
    # slash was trimmed off a real path.
    #
    # Nothing else in section 1.1 sits under `/api/auth`. The `/api/users` tree
    # is a separate prefix, which row 31 moved to its own entry below, and a
    # route key matches literally rather than by substring, so neither cut pulls
    # any of the other along.
    identity = ["/api/auth"]
    # Row 29. Four prefixes and the largest cut of the nine by route count: 43
    # routes, against row 26's 34 and `moderation`'s 20. Like row 26's four they
    # are four sibling trees rather than one tree with children, so they are four
    # prefixes and not one: `/api/parts` is the centre of the domain model but
    # nothing else in the URL space sits below it.
    #
    # API Gateway matches a route key literally rather than by string prefix, so
    # `/api/parts` does not claim `/api/part-manufacturers` even though one is a
    # character prefix of the other, and neither claims row 21's
    # `/api/part-price-alerts`, which is a fourth tree on the same stem and stays
    # on `admin`. `/api/categories` and `/api/retailers` are independent of all
    # three. No ordering between any of them is implied.
    #
    # Eight route keys, a bare and a `{proxy+}` for each of the four, and this is
    # the cut where the most routes ride the bare keys: seven of the 43, against
    # row 26's two and row 27's none. Every one of the seven is a trailing-slash
    # route rather than a route at the bare path, which is the same trap row 21
    # sprang on `/api/part-price-alerts` and row 26 on `/api/build-lists`.
    # `parts.py`, `part_manufacturers.py` and `retailers.py` each declare a
    # `POST "/"` and a generated or hand-written `GET "/"`, and `categories.py`
    # declares a `GET "/"`, so those seven mount at `/api/parts/`,
    # `/api/part-manufacturers/`, `/api/retailers/` and `/api/categories/`. API
    # Gateway normalises the trailing slash onto the bare key and a route key may
    # not itself end in a slash, so the bare key is the only spelling that
    # matches them, and writing the path with its slash is an apply-time
    # BadRequestException on a plan that was green. None of the four bare keys is
    # defensive here.
    #
    # `/api/parts/{entity_id}` and the hand-written `/api/parts/with-votes`,
    # `/count`, `/check-url`, `/filter-options` and
    # `/find-by-part-manufacturer-and-part-number` are section 1.4's ordering
    # concern for this domain, and they survive untouched because the `{proxy+}`
    # key hands the whole subtree to one function: `parts.py` registers the
    # literal paths before the generated `{entity_id}`, and FastAPI keeps
    # deciding exactly as it does on the monolith today. Splitting the subtree
    # across route keys is what would break it, and nothing here does.
    catalog = ["/api/parts", "/api/part-manufacturers", "/api/categories", "/api/retailers"]
    # Row 31, the last cut. Two prefixes and 14 routes: 12 under `/api/users`
    # and 2 under `/api/app-settings`. They are two sibling trees rather than
    # one tree with children, so they are two prefixes and not one, and neither
    # is under the other in the URL space.
    #
    # Four route keys, a bare and a `{proxy+}` for each. Both bare keys carry
    # real traffic and neither is defensive. `users.py` declares a `GET "/"` and
    # a `POST "/"` and `app_settings.py` declares a `GET "/"` and a `PUT "/"`,
    # so those four mount at `/api/users/` and `/api/app-settings/`. API Gateway
    # normalises the trailing slash onto the bare key and a route key may not
    # itself end in a slash, so the bare key is the only spelling that matches
    # them; writing the path with its slash is an apply-time BadRequestException
    # on a plan that was green, which is the trap row 21 sprang on
    # `/api/part-price-alerts` and row 26 on `/api/build-lists`. Ten of the 14
    # ride the `{proxy+}` keys, all ten of them under `/api/users`, which leaves
    # `/api/app-settings/{proxy+}` as the one key on this cut that matches
    # nothing today. It is generated rather than chosen, because
    # `local.lambda_domain_route_keys` makes a pair per prefix, and it is
    # harmless: it points at the same integration as its bare key, so a request
    # under it reaches a healthy function and gets that function's own 404.
    #
    # `/api/users/admin/users` is section 1.4's ordering hazard for this domain
    # and it survives untouched, for the reason every cut with an ordering
    # concern has recorded: the `{proxy+}` key hands the whole subtree to one
    # function, so FastAPI keeps deciding exactly as it does on the monolith
    # today. It is worth naming because this one resolves on shape rather than
    # on registration order, which is more fragile than the `catalog` case:
    # `GET /{user_id}` is registered *before* `GET /admin/users`, and the only
    # reason the literal wins is that `/admin/users` is two segments and
    # `/{user_id}` is one. A bare `/api/users/admin` really does match
    # `{user_id}`, as section 1.4 says. Nothing here changes that either way,
    # and splitting the subtree across route keys is what would break it.
    #
    # `/api/auth` is row 27's and stays there, and the `/api/users` tree that
    # row 27's comment said this row would move is exactly what moves here.
    users = ["/api/users", "/api/app-settings"]
  }

  # Two route keys per prefix, generated rather than written out, so a domain added above cannot be
  # left with one half of a pair.
  lambda_domain_route_keys = merge([
    for name in local.routed_lambda_domains : {
      for key in flatten([
        for prefix in local.lambda_domain_path_prefixes[name] : [
          "ANY ${prefix}",
          "ANY ${prefix}/{proxy+}",
        ]
      ]) : key => { integration = name }
    }
  ]...)
}

module "api" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/http-api"
  version = "~> 2.0"

  name        = "${local.prefix}-api"
  description = "CarModPicker ${var.environment} API (Lambda proxy)"

  # Every domain that has been cut, and nothing else. Row 32 removed the "legacy" entry along with
  # the monolith it named. The entries are generated from module.lambda_domain rather than written
  # out one at a time, so a domain named in local.routed_lambda_domains cannot be left without an
  # integration.
  #
  # Until row 32 this map carried a hand-written "legacy" key alongside the generated ones, spelled
  # exactly that way because the module ships two moved blocks carrying the 1.x integration and
  # invoke permission to that key, so adopting 2.0 moved both resources instead of replacing them.
  # That adoption is long done and the key is gone with the function.
  #
  # A domain's invoke permission is "AllowAPIGatewayInvoke-<domain>", which is unchanged by the
  # monolith leaving. The module gives the bare, unsuffixed statement id to the default_integration
  # entry, or to the only integration when there is exactly one; with nine integrations and no
  # default_integration neither case applies, so all nine keep the suffixed ids they already have
  # in state and no permission is replaced. Section 3.5.
  integrations = {
    for name in local.routed_lambda_domains : name => {
      lambda_function_name = module.lambda_domain[name].function_name
      lambda_invoke_arn    = module.lambda_domain[name].invoke_arn
      # 29 seconds, the same ceiling the domain function's own timeout is set to in
      # lambda_domains.tf. A longer function timeout would be invisible because the gateway gives
      # up first.
      timeout_milliseconds = 29000
    }
  }

  # No $default route at all, which is what retiring the monolith means at the gateway. The module
  # documents null as exactly this: "Set it to null to create no $default route at all, which makes
  # the API answer 404 for anything the explicit routes do not match. Only do that once the
  # migration is finished." Rows 14 through 31 finished it; all nine domains carry their own keys.
  #
  # What this gives up, stated plainly rather than left to be discovered. The five root routes
  # `add_root_routes` puts on every application, `/`, `/health`, `/ready`, `/sitemap.xml` and
  # `/sitemap-{name}.xml`, were the only paths still resolving through $default, and they now have
  # no route key and answer 404 from the gateway. That is a deliberate narrowing and not an
  # oversight:
  #
  #   - Nothing calls them through this API. The deploy workflow's smoke probe reaches `/health`
  #     with `aws lambda invoke` and a synthesised HTTP API event, never over HTTP through the
  #     gateway, so `smoke-domains` is unaffected. `scripts/verify_route_cut.sh` probes the nine
  #     domain prefixes, all of which keep their keys. No Route 53 health check, CloudFront
  #     behaviour or alarm targets any of the five.
  #   - `frontend/src/api/utility.ts` exports a `healthCheck()` calling `/health`, and no component
  #     imports it. It is dead in the frontend today and is left alone here rather than deleted in
  #     a backend PR; row 33 is the frontend row.
  #   - The sitemap pair was never reachable anyway. `sitemap_service.py` bypasses the repository
  #     bundle, so no domain was granted the three tables it reads, and every cut since row 14
  #     recorded the pair as unreachable-through-the-gateway on purpose. A 404 is a better answer
  #     than the AccessDeniedException a route key would have produced. `frontend/public/sitemap.xml`
  #     is a static file served by CloudFront from the frontend bucket and is untouched by this.
  #
  # Giving the five a home is a decision to make on its own if one is ever wanted, and the shape is
  # a route key per path pointing at one nominated domain plus that domain's missing S3 and table
  # grants. It is deliberately not smuggled into the row that removes the monolith.
  default_integration = null

  # Two keys per cut prefix: `media`'s pair from row 14, `build-logs`' pair from row 18,
  # `moderation`'s three pairs from row 19, `vehicles`' two pairs from row 20, `admin`'s four
  # pairs from row 21, `build-lists`' four pairs from row 26, `identity`'s one pair from row 27,
  # `catalog`'s four pairs from row 29 and `users`' two pairs from row 31, which completes the
  # nine. No
  # authorization_type is set on any of them, which means the module's own choice, CUSTOM whenever
  # authorizer_id is set, so each one sits behind the staging access gate exactly as $default does.
  # Setting NONE here would punch a hole straight past the gate, which is the failure the module's
  # own comment records from the Portfolio inventory.
  routes = local.lambda_domain_route_keys

  throttling_burst_limit    = var.api_throttle_burst_limit
  throttling_rate_limit     = var.api_throttle_rate_limit
  access_log_retention_days = 7
  # access_log_format and lambda_permission_statement_id: the module defaults are our values.

  # Behind the staging access gate the API is reachable only through its custom domain; the
  # execute-api URL would bypass the authorizer's host, so it is disabled. The gate's REQUEST
  # authorizer runs on every route and admits an OPTIONS preflight, a call carrying the
  # origin-verify header (pipelines, health checks), or a browser call carrying the gate's
  # signed cookies.
  disable_execute_api_endpoint = local.staging_gate_enabled
  authorizer_id                = local.staging_gate_enabled ? module.staging_access_gate[0].http_api_authorizer_id : null

  domain_name      = local.custom_domain ? "api.${local.domain_name}" : null
  certificate_arn  = module.api_certificate.certificate_arn
  zone_id          = local.custom_domain ? module.staging_dns.zone_id : null
  domain_name_tags = { Name = "${local.prefix}-api-domain" }
}
