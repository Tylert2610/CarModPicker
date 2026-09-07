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
