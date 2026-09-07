# The alarm SNS topic, its email subscriptions and the Lambda, HTTP API and DynamoDB alarms all
# come from the shared api-alarms module. Every threshold, period and evaluation count is the
# module default and matches state, so none of them is passed here.
module "alarms" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/api-alarms"
  version = "~> 1.6"

  name_prefix         = local.prefix
  notification_emails = ["tyler@webbpulse.com", "tylert2610@gmail.com"]

  lambda_function_name = module.lambda_api.function_name
  http_api_id          = module.api.api_id

  # Keyed by the dynamodb_tables.json key so each alarm keeps the address it has in state; the
  # value is the real table name, which is what "<table name>-throttles" is built from.
  dynamodb_tables = { for k, t in module.dynamodb.tables : k => t.name }
}

moved {
  from = aws_sns_topic.alarms
  to   = module.alarms.aws_sns_topic.alarms
}

moved {
  from = aws_sns_topic_subscription.alarms_tyler_webb
  to   = module.alarms.aws_sns_topic_subscription.email["tyler@webbpulse.com"]
}

moved {
  from = aws_sns_topic_subscription.alarms_tyler_gmail
  to   = module.alarms.aws_sns_topic_subscription.email["tylert2610@gmail.com"]
}

moved {
  from = aws_cloudwatch_metric_alarm.lambda_errors
  to   = module.alarms.aws_cloudwatch_metric_alarm.lambda_errors[0]
}

moved {
  from = aws_cloudwatch_metric_alarm.lambda_throttles
  to   = module.alarms.aws_cloudwatch_metric_alarm.lambda_throttles[0]
}

moved {
  from = aws_cloudwatch_metric_alarm.api_5xx
  to   = module.alarms.aws_cloudwatch_metric_alarm.api_5xx[0]
}

moved {
  from = aws_cloudwatch_metric_alarm.api_integration_latency_p99
  to   = module.alarms.aws_cloudwatch_metric_alarm.api_integration_latency[0]
}

moved {
  from = aws_cloudwatch_metric_alarm.dynamodb_throttles
  to   = module.alarms.aws_cloudwatch_metric_alarm.dynamodb_throttles
}
