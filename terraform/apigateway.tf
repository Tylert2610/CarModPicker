# The HTTP API: the API itself, the $default stage with throttling and the JSON access log, the
# Lambda proxy integrations and their invoke permissions, the routes, and the custom domain with
# its mapping and alias record. All from the shared platform module.
#
# Section 3.5 and section 6 of docs/migration/split-plan.md: the strangler runs through this file.
# Each cut adds route keys for one domain and the monolith keeps everything else through $default,
# so a cut is one entry in local.routed_lambda_domains plus that domain's route keys, and a
# rollback is deleting them again.

locals {
  # Domains that have been cut over, in the order section 6.1 cuts them. A domain belongs here only
  # once local.lambda_domain_route_keys names its route keys: the module's every_integration_is_routed
  # check fails the plan on an integration no route can reach, so the two move together.
  #
  # Row 14 is `media`, row 18 is `build-logs` and row 19 is `moderation`. Rows 20 through 31
  # append vehicles, admin, build-lists, identity, catalog and users.
  routed_lambda_domains_declared = ["media", "build-logs", "moderation"]

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

  # The monolith plus every domain that has been cut. The per-domain entries are generated from
  # module.lambda_domain rather than written out one at a time, so a domain named in
  # local.routed_lambda_domains cannot be left without an integration.
  #
  # The key must be "legacy" for the monolith: the module ships the two moved blocks that carry the
  # 1.x integration and invoke permission to that exact key, so adopting 2.0 moves both resources
  # instead of replacing them.
  #
  # A domain's own invoke permission gets the statement id "AllowAPIGatewayInvoke-<domain>" from the
  # module, because the bare id stays with the default_integration. That is what keeps the
  # monolith's existing permission untouched by this change.
  integrations = merge(
    {
      legacy = {
        lambda_function_name = module.lambda_api.function_name
        lambda_invoke_arn    = module.lambda_api.invoke_arn
        timeout_milliseconds = 29000
      }
    },
    {
      for name in local.routed_lambda_domains : name => {
        lambda_function_name = module.lambda_domain[name].function_name
        lambda_invoke_arn    = module.lambda_domain[name].invoke_arn
        # 29 seconds, the same ceiling the domain function's own timeout is set to in
        # lambda_domains.tf. A longer function timeout would be invisible because the gateway gives
        # up first.
        timeout_milliseconds = 29000
      }
    },
  )

  # The monolith stays on $default for the whole migration. API Gateway matches a full route key
  # first, then a greedy {proxy+}, then $default last, so everything not named in routes keeps
  # falling through to the monolith and a rollback is deleting the routes entry again. Section 6.4.
  default_integration = "legacy"

  # Two keys per cut prefix: `media`'s pair from row 14, `build-logs`' pair from row 18 and
  # `moderation`'s three pairs from row 19. No
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
