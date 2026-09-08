# The alarm SNS topic, its email subscriptions and the Lambda, HTTP API and DynamoDB alarms all
# come from the shared api-alarms module. Every threshold, period and evaluation count is the
# module default and matches state, so none of them is passed here.

locals {
  # The functions the aggregate Lambda alarms sum over: the nine domains, and deliberately not the
  # monolith. Section 3.6 and open question 1, answered on 2026-09-08.
  #
  # Order is load bearing and is not cosmetic. The module builds one CloudWatch metric math
  # expression over positionally named metric ids, m0, m1 and so on, so reordering the list
  # rewrites every expression on an existing alarm. This filters `local.lambda_domain_names` in
  # ecr.tf rather than listing names here, which gets both properties for free: the order is that
  # list's order, which is section 6.1's cut order and is already declared load bearing there, and
  # a domain added by rows 18 through 31 joins the alarm by appending to the end rather than by an
  # edit here that could be forgotten or could reorder what is already alarmed.
  #
  # The filter is what keeps the list to functions that exist. `local.lambda_domain_names` is all
  # nine from row 9 onward because nine ECR repositories exist, while `local.lambda_domains` in
  # lambda_domains.tf holds only the domains whose function has actually been created, which today
  # is `media` alone. A name in the metric math for a function that does not exist would resolve to
  # a metric that never reports, which is not an error but is an alarm claiming coverage it does
  # not have.
  #
  # Nine is under the module's chunk size of 10, so this is one errors alarm and one throttles
  # alarm for the whole estate for the life of the migration, with no chunking and no second alarm
  # pair to subscribe or document.
  alarm_lambda_function_names = [
    for name in local.lambda_domain_names : module.lambda_domain[name].function_name
    if contains(keys(local.lambda_domains), name)
  ]

  # The log groups the error metric filters read: the monolith's, plus one per created domain
  # function, the same shape and the same source as the fail open list below. A metric filter is
  # created against a named log group that must already exist, so this keys off
  # `local.lambda_domains` and not off the nine names.
  alarm_error_log_groups = merge(
    { api = module.lambda_api.log_group_name },
    { for name in keys(local.lambda_domains) : name => module.lambda_domain[name].log_group_name },
  )
}

module "alarms" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/api-alarms"
  version = "~> 2.4"

  name_prefix         = local.prefix
  notification_emails = ["tyler@webbpulse.com", "tylert2610@gmail.com"]

  http_api_id = module.api.api_id

  # The many function form. `lambda_function_name` is gone, and the two are mutually exclusive by
  # the module's own validation, so this is the switch from a per function alarm pair to the two
  # aggregate alarms rather than an addition alongside them.
  #
  # What that costs, stated plainly: the monolith's own "<prefix>-lambda-errors" and
  # "<prefix>-lambda-throttles" alarms are destroyed by this change and the monolith is not in the
  # aggregate. Keeping them would have meant either leaving `lambda_function_name` set, which the
  # validation refuses alongside `lambda_function_names`, or adding the monolith to the aggregate
  # list, which is the thing section 3.6's ceiling discussion and the decision on open question 1
  # both rule out: it spends a slot on a function that rows 18 through 31 are retiring, and it
  # makes "the backend is erroring" mean "the backend or the thing the backend is being moved off
  # is erroring".
  #
  # `lambda_errors_alarm_function_name` is the module's own escape hatch for wanting the errors
  # half on its own, and it is deliberately not used: it creates an alarm named
  # "<prefix>-lambda-errors", which is the same alarm this change is destroying, so it would buy
  # the errors half back at the cost of the destroy-and-create being a no-op that hides the
  # decision rather than recording it.
  #
  # The monolith is not uncovered in the meantime. Until row 31 retires it, the monolith serves
  # every route the nine domains have not been cut yet, so an invocation error in it is a 5xx
  # through the gateway, and "<prefix>-api-5xx" fires on exactly that. It also keeps its own log
  # group in `error_log_groups` below, so anything it logs at ERROR still reaches
  # "<prefix>-application-errors", and its rate limiter still reaches
  # "<prefix>-rate-limit-failed-open". What it loses is the AWS/Lambda Errors and Throttles signal
  # specifically, which is the narrower of the two: an error that never reaches the gateway as a
  # 5xx is an init failure or a timeout, and the API 5xx alarm sees both of those as well.
  lambda_function_names      = local.alarm_lambda_function_names
  lambda_aggregate_alarm     = true
  lambda_aggregate_threshold = 0

  # One "<prefix>-dynamodb-throttles" alarm covering read and write throttling across every table
  # in the environment, instead of one alarm per table. With 25 tables the per-table shape was 25
  # alarms and 50 billable alarm metrics; this is one alarm that also picks up new tables without
  # a Terraform change. dynamodb_tables stays empty because the aggregate alarm needs no list.
  dynamodb_aggregate_alarm = true
  dynamodb_tables          = {}

  # AWS/Lambda Errors only counts an invocation that raised. It says nothing about a request the
  # function handled and logged an error for, which is most of what actually goes wrong. This
  # metric filter reads each log group and the one "<prefix>-application-errors" alarm fires on the
  # total count. Both the filter pattern and the alarm thresholds are module defaults.
  #
  # The default pattern is { $.level = "ERROR" }, which only matches events that parse as JSON.
  # That holds in every group here: the monolith runs with log_format = "JSON" and each domain
  # function is created with log_format = "JSON" in lambda_domains.tf, and app/core/logging.py
  # installs a JsonFormatter with rename_fields levelname -> level on the non-TTY path, so every
  # record is JSON with a top level "level" key.
  #
  # This now covers the domain functions as well as the monolith, which is what makes it the alarm
  # that scales: every filter writes the same dimensionless metric, so the alarm is a plain Sum
  # across all of them and has no metric math ceiling to run into as rows 18 through 31 add the
  # remaining eight log groups.
  error_log_groups = local.alarm_error_log_groups

  # The shared DynamoDB backed limiter in app/api/middleware/shared_rate_limiter.py allows a
  # request when it cannot reach "<prefix>-rate-limits", rather than refusing traffic. Nothing
  # reported that: the request succeeded, so AWS/Lambda Errors stays at zero and the API returns
  # 200 while the limit is not being enforced. This is one metric filter per log group below and
  # one "<prefix>-rate-limit-failed-open" alarm on the metric they share.
  rate_limit_fail_open_alarm = true

  # The limiter is installed as global middleware in app/main.py, so it runs in the monolith and
  # in every domain function. This is the same set of log groups the error filters read, and it is
  # given explicitly rather than left to default to error_log_groups so that the two lists stay
  # independently readable if one of them ever needs to diverge.
  rate_limit_fail_open_log_groups = local.alarm_error_log_groups

  # rate_limit_fail_open_filter_pattern is deliberately not set: the module default
  # { $.rate_limit_failed_open IS TRUE } is now correct. _failed_open in shared_rate_limiter.py
  # passes the flag through extra=, and webbpulse.logging.JsonFormatter copies every non-reserved
  # LogRecord attribute to the top level of the emitted object, so the record reads
  #
  #   {"level":"WARNING","message":"Shared rate limit check failed; allowing the request. ...",
  #    "rate_limit_failed_open":true,"rate_limit_operation":"record_request","client_key":"...",
  #    "route":"...","exception_type":"...",...}
  #
  # which is a real JSON boolean at the top level, exactly what IS TRUE selects on. This replaces
  # the "rate_limit_failed_open=True" substring override that stood in while the flag was still
  # interpolated into the message text, where a JSON filter pattern could not see it.
}
