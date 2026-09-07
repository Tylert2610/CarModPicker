# The HTTP API: the API itself, the $default stage with throttling and the JSON access log, the
# Lambda proxy integration and its invoke permission, the $default route, and the custom domain
# with its mapping and alias record. All from the shared platform module.
module "api" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/http-api"
  version = "~> 1.3"

  name        = "${local.prefix}-api"
  description = "CarModPicker ${var.environment} API (Lambda proxy)"

  lambda_invoke_arn    = aws_lambda_function.api.invoke_arn
  lambda_function_name = aws_lambda_function.api.function_name

  route_keys                       = ["$default"]
  integration_timeout_milliseconds = 29000
  throttling_burst_limit           = var.api_throttle_burst_limit
  throttling_rate_limit            = var.api_throttle_rate_limit
  access_log_retention_days        = 14
  # access_log_format and lambda_permission_statement_id: the module defaults are our values.

  # Behind the staging access gate the API is reachable only through its custom domain; the
  # execute-api URL would bypass the authorizer's host, so it is disabled. The gate's REQUEST
  # authorizer runs on every route and admits an OPTIONS preflight, a call carrying the
  # origin-verify header (pipelines, health checks), or a browser call carrying the gate's
  # signed cookies.
  disable_execute_api_endpoint = local.staging_gate_enabled
  authorizer_id                = local.staging_gate_enabled ? module.staging_access_gate[0].http_api_authorizer_id : null

  domain_name      = local.custom_domain ? "api.${local.domain_name}" : null
  certificate_arn  = local.custom_domain ? aws_acm_certificate_validation.api[0].certificate_arn : null
  zone_id          = local.custom_domain ? module.staging_dns.zone_id : null
  domain_name_tags = { Name = "${local.prefix}-api-domain" }
}
