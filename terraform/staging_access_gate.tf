# Staging access gate: Cognito sign-in plus CloudFront signed cookies in front of the staging
# site and its API. Only exists when WebbPulse-Platform sets staging_access_gate = true on a
# staging workspace with a custom domain. Production never instantiates it, so every reference
# in cloudfront.tf, apigateway.tf and iam_github_actions.tf is gated on local.staging_gate_enabled.
#
# cloudfront_distribution_arn is left unset on purpose: aws_cloudfront_distribution.frontend
# consumes this module's outputs, so naming it here would be a dependency cycle. The login
# function URL permission then admits any distribution in the (single-application) staging account.
module "staging_access_gate" {
  count = local.staging_gate_count

  source = "app.terraform.io/WebbPulse/platform-modules/aws//modules/staging-access-gate"

  # 2.9 for identity_jwt and identity_jwt_route_keys, which is how a gated environment enforces the
  # identity access token at all. Every release between 1.1 and 2.9 is additive for this module:
  # 2.3.0 read the region as `region` and required provider 6.x, which this root already does, and
  # 2.9.0 added exactly the two inputs below and nothing else. The module merges the new
  # environment variables rather than setting them empty, so the bump alone changes nothing but the
  # authorizer function's source hash and description; what changes behaviour is the two inputs
  # below being non-empty.
  version = "~> 2.9"

  name             = local.prefix
  cookie_domain    = local.domain_name
  site_host        = "www.${local.domain_name}"
  additional_hosts = [local.domain_name]
  allowed_emails   = var.staging_access_users
  http_api_id      = module.api.api_id
  invite_login_url = "https://www.${local.domain_name}/"

  # The application's own viewer-request logic (apex to www 301, prerender URI rewrites) runs
  # inside the gate function before the session check.
  viewer_request_handler_js = templatefile("${path.module}/cloudfront_functions/app_handler.js.tftpl", { domain = local.active_domain })

  # Row 8: identity access token enforcement, staging's half of it.
  #
  # This is where the gate mode does its work. Every route on this API already carries this
  # module's REQUEST authorizer and an HTTP API route takes exactly one authorizer, so the native
  # JWT authorizer that production will use has no slot here. The gate's own Lambda does both
  # checks instead: the signed cookie first, exactly as before, and then a valid Bearer access
  # token on the routes named below. The gate check still runs first and still has to pass, so this
  # only ever narrows access and can never open anything, and the x-origin-verify bypass that
  # pipelines and health checks use is untouched.
  #
  # The issuer and the audience are the same two locals module.identity is configured with in
  # terraform/identity.tf and the same two module.api would be given in native mode, for the same
  # reason: byte identity with what the signer stamps is the entire requirement, and a second
  # spelling of either is a token that verifies nowhere. jwks_url is left to the module, which
  # derives <issuer>/.well-known/jwks.json, and that is the URL this product actually serves,
  # because local.identity_issuer is built from the API custom domain and the discovery document
  # builds jwks_uri the same way.
  identity_jwt = local.identity_jwt_gate_enforced ? {
    issuer   = local.identity_issuer
    audience = local.identity_audience
  } : null

  # THE ROUTE KEYS COME FROM module.api RATHER THAN BEING RESTATED HERE, and that is the whole of
  # the wiring. The output is the set of routes marked require_identity_jwt in
  # terraform/apigateway.tf, already sorted, and a route key is the same string on both sides by
  # construction: it is the map key in that module's routes and it is requestContext.routeKey in
  # this authorizer's event. Listing the fifteen keys again here would be a second place for the
  # set to drift from the routes it is supposed to describe.
  #
  # Empty in every mode but gate, which is what leaves the authorizer checking only the gate
  # credentials. Both halves have to be set for anything to be enforced: the module's
  # identity_jwt_enforced output is the AND of them.
  identity_jwt_route_keys = local.identity_jwt_gate_enforced ? module.api.identity_jwt_route_keys : []
}
