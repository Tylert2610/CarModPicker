# The HTTP API: the API itself, the $default stage with throttling and the JSON access log, the
# Lambda proxy integration and its invoke permission, the $default route, and the custom domain
# with its mapping and alias record. All from the shared platform module.
module "api" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/http-api"
  version = "~> 2.0"

  name        = "${local.prefix}-api"
  description = "CarModPicker ${var.environment} API (Lambda proxy)"

  # One backend, everything on $default. The key must be "legacy": the module ships the two moved
  # blocks that carry the 1.x integration and invoke permission to that exact key, so adopting 2.0
  # moves both resources instead of replacing them.
  integrations = {
    legacy = {
      lambda_function_name = module.lambda_api.function_name
      lambda_invoke_arn    = module.lambda_api.invoke_arn
      timeout_milliseconds = 29000
    }
  }

  default_integration = "legacy"

  # routes stays empty: nothing is carved off the monolith yet, so $default serves every path.
  routes = {}

  throttling_burst_limit    = var.api_throttle_burst_limit
  throttling_rate_limit     = var.api_throttle_rate_limit
  access_log_retention_days = 14
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
