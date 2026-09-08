# The alarm SNS topic, its email subscriptions and the Lambda, HTTP API and DynamoDB alarms all
# come from the shared api-alarms module. Every threshold, period and evaluation count is the
# module default and matches state, so none of them is passed here.
module "alarms" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/api-alarms"
  version = "~> 2.4"

  name_prefix         = local.prefix
  notification_emails = ["tyler@webbpulse.com", "tylert2610@gmail.com"]

  lambda_function_name = module.lambda_api.function_name
  http_api_id          = module.api.api_id

  # One "<prefix>-dynamodb-throttles" alarm covering read and write throttling across every table
  # in the environment, instead of one alarm per table. With 25 tables the per-table shape was 25
  # alarms and 50 billable alarm metrics; this is one alarm that also picks up new tables without
  # a Terraform change. dynamodb_tables stays empty because the aggregate alarm needs no list.
  dynamodb_aggregate_alarm = true
  dynamodb_tables          = {}

  # AWS/Lambda Errors only counts an invocation that raised. It says nothing about a request the
  # function handled and logged an error for, which is most of what actually goes wrong. This
  # metric filter reads the function's own log group and the one "<prefix>-application-errors"
  # alarm fires on the count. Both the filter pattern and the alarm thresholds are module
  # defaults.
  #
  # The default pattern is { $.level = "ERROR" }, which only matches events that parse as JSON.
  # That holds here: the function runs with log_format = "JSON", and app/core/logging.py installs
  # a JsonFormatter with rename_fields levelname -> level on the non-TTY path, so every record in
  # this log group is JSON with a top level "level" key.
  error_log_groups = { api = module.lambda_api.log_group_name }

  # The shared DynamoDB backed limiter in app/api/middleware/shared_rate_limiter.py allows a
  # request when it cannot reach "<prefix>-rate-limits", rather than refusing traffic. Nothing
  # reported that: the request succeeded, so AWS/Lambda Errors stays at zero and the API returns
  # 200 while the limit is not being enforced. This is one metric filter per log group below and
  # one "<prefix>-rate-limit-failed-open" alarm on the metric they share.
  rate_limit_fail_open_alarm = true

  # The limiter is installed as global middleware in app/main.py, so it runs in the monolith and
  # in every domain function. error_log_groups only covers the monolith, so the list is given
  # explicitly here rather than defaulting to it.
  rate_limit_fail_open_log_groups = merge(
    { api = module.lambda_api.log_group_name },
    { for name in keys(local.lambda_domains) : name => module.lambda_domain[name].log_group_name },
  )

  # NOT the module default. The default { $.rate_limit_failed_open IS TRUE } matches a top level
  # JSON field, and this service does not emit one: _failed_open in shared_rate_limiter.py builds
  # a printf style message and interpolates the flag into the message text, so the record reads
  #
  #   {"level":"WARNING","message":"Shared rate limit check failed; allowing the request.
  #    rate_limit_failed_open=True operation=check ...", ...}
  #
  # A JSON filter pattern selects on fields and cannot see inside the message string, so the
  # default would match nothing here: the metric would sit flat at 0 and the alarm would report
  # healthy while the limiter was failing open. A quoted pattern is a plain substring match over
  # the whole raw event, which does match. It is case sensitive, and Python's %s interpolation of
  # a bool renders "True", not "true".
  #
  # The better fix is at the source: emit the flag as a real log record field, the way Portfolio's
  # limiter does, and drop this override for the module default. That is a backend change and does
  # not belong in the same PR as the alarm.
  rate_limit_fail_open_filter_pattern = "\"rate_limit_failed_open=True\""
}
