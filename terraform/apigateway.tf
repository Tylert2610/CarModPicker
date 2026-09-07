resource "aws_apigatewayv2_api" "api" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"
  description   = "CarModPicker ${var.environment} API (Lambda proxy)"

  # Behind the staging access gate the API is reachable only through its custom domain, which
  # CloudFront calls with the origin-verify header; the execute-api URL would bypass that.
  disable_execute_api_endpoint = local.staging_gate_enabled
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.prefix}-api"
  retention_in_days = 14
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"

  # Staging access gate: the module's REQUEST authorizer admits only requests carrying the
  # origin-verify header CloudFront adds, so api.staging.<domain> cannot be called around the gate.
  authorization_type = local.staging_gate_enabled ? "CUSTOM" : "NONE"
  authorizer_id      = local.staging_gate_enabled ? module.staging_access_gate[0].http_api_authorizer_id : null
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = var.api_throttle_burst_limit
    throttling_rate_limit  = var.api_throttle_rate_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId               = "$context.requestId"
      requestTime             = "$context.requestTime"
      ip                      = "$context.identity.sourceIp"
      userAgent               = "$context.identity.userAgent"
      httpMethod              = "$context.httpMethod"
      path                    = "$context.path"
      routeKey                = "$context.routeKey"
      protocol                = "$context.protocol"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      responseLatency         = "$context.responseLatency"
      integrationLatency      = "$context.integrationLatency"
      integrationStatus       = "$context.integrationStatus"
      integrationErrorMessage = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

resource "aws_apigatewayv2_domain_name" "api" {
  count = local.custom_domain ? 1 : 0

  domain_name = "api.${local.domain_name}"

  domain_name_configuration {
    certificate_arn = aws_acm_certificate_validation.api[0].certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }

  tags = { Name = "${local.prefix}-api-domain" }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  count = local.custom_domain ? 1 : 0

  api_id      = aws_apigatewayv2_api.api.id
  domain_name = aws_apigatewayv2_domain_name.api[0].id
  stage       = aws_apigatewayv2_stage.default.id
}
