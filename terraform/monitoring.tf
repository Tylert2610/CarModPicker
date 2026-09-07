# ---------------------------------------------------------------------------
# SNS Topic — shared alarm notification target
# Both email addresses must confirm their subscription after the first apply.
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alarms" {
  name = "${local.prefix}-alarms"
}

resource "aws_sns_topic_subscription" "alarms_tyler_webb" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tyler@webbpulse.com"
}

resource "aws_sns_topic_subscription" "alarms_tyler_gmail" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tylert2610@gmail.com"
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms — Lambda + HTTP API + DynamoDB
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.prefix}-lambda-errors"
  alarm_description   = "Lambda API reported invocation errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.prefix}-lambda-throttles"
  alarm_description   = "Lambda API invocations were throttled"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.prefix}-api-5xx"
  alarm_description   = "HTTP API returned 5xx responses"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = module.api.api_id }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_integration_latency_p99" {
  alarm_name          = "${local.prefix}-api-integration-latency-p99"
  alarm_description   = "HTTP API p99 integration latency above 10 s"
  namespace           = "AWS/ApiGateway"
  metric_name         = "IntegrationLatency"
  dimensions          = { ApiId = module.api.api_id }
  extended_statistic  = "p99"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  for_each = aws_dynamodb_table.tables

  alarm_name          = "${each.value.name}-throttles"
  alarm_description   = "DynamoDB read or write throttle events on ${each.value.name}"
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  metric_query {
    id          = "throttles"
    expression  = "reads + writes"
    label       = "ThrottleEvents"
    return_data = true
  }

  metric_query {
    id = "reads"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "ReadThrottleEvents"
      dimensions  = { TableName = each.value.name }
      stat        = "Sum"
      period      = 300
    }
  }

  metric_query {
    id = "writes"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "WriteThrottleEvents"
      dimensions  = { TableName = each.value.name }
      stat        = "Sum"
      period      = 300
    }
  }
}
