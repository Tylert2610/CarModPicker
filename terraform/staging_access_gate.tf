# Staging access gate: Cognito sign-in plus CloudFront signed cookies in front of the staging
# site and its API. Only exists when WebbPulse-Platform sets staging_access_gate = true on a
# staging workspace with a custom domain. Production never instantiates it, so every reference
# in cloudfront.tf, apigateway.tf and iam_github_actions.tf is gated on local.staging_gate_enabled.
#
# cloudfront_distribution_arn is left unset on purpose: module.frontend consumes this module's
# outputs through its access_gate argument, so naming it here would be a dependency cycle. The login
# function URL permission then admits any distribution in the (single-application) staging account.
module "staging_access_gate" {
  count = local.staging_gate_count

  source = "app.terraform.io/WebbPulse/platform-modules/aws//modules/staging-access-gate"
  # Pinned exactly: 1.3.2 adds aws_lambda_permission.login_invoke, a real new resource on the
  # login function URL. That is a change to apply on its own, not something to fold into a
  # state-move-only change. Relax this to ~> 1.3 in the change that adopts it.
  version = "1.3.1"

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
}
