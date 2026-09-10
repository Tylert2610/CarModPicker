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
  # lambda_domains.tf holds only the domains whose function has actually been created, which after
  # row 28 is `media`, `build-logs`, `moderation`, `vehicles`, `admin`, `build-lists` and
  # `identity`. With the three consumers from rows 24, 25 and 28 that is ten of the ten slots used
  # and none left, which the ceiling paragraph below spends. A name in the metric math for a function that does not exist would
  # resolve to a metric that never reports, which is not an error but is an alarm claiming coverage
  # it does not have. It is also empty in a fresh account bootstrapping with an empty
  # `bootstrap_image_tag`, which is why `lambda_aggregate_alarm` below is conditional rather than
  # true.
  #
  # The chunk ceiling, and how to count against it. The module chunks this list into groups of ten
  # and creates one alarm pair per group, so the eleventh name here creates a second pair,
  # `<prefix>-lambda-errors-aggregate-2` and `<prefix>-lambda-throttles-aggregate-2`. Chunk zero
  # keeps its unsuffixed names and its m0 through m9 expression, so crossing the ceiling adds
  # alarms rather than rewriting the ones already subscribed.
  #
  # Count created functions, not declared ones. Row 24's note in the split plan predicted that row
  # 25 would be the eleventh and would cross this, by counting the nine names in
  # `local.lambda_domain_names`. The filter below is what makes that wrong: it admits only the
  # domains whose function actually exists. With rows 18 through 21, 26 and 27 cut that is seven
  # domains, so rows 24, 25 and 28's consumers bring this list to ten, and ten is exactly the chunk
  # size.
  #
  # Row 28 fills the last slot, and it is the row where the ceiling stops being a later problem.
  # Chunk zero is now full, so the next function created is the eleventh and produces
  # `<prefix>-lambda-errors-aggregate-2` and `<prefix>-lambda-throttles-aggregate-2` while leaving
  # chunk zero's m0 through m9 expression untouched. On the current cut order that is row 29's
  # `catalog`, which is the next row. The decision is due now rather than soon: either accept a
  # second pair, or give the stream consumers an aggregate of their own, which buys a tidier
  # notification at the cost of a second module invocation, a second topic decision and a threshold
  # to reason about twice. Moving the three consumers out is the cheaper of the two, and it is the
  # option that keeps all nine domains in one expression, which is the grouping an operator
  # actually wants to read.
  #
  # The consumers are appended after the domains rather than sorted in among them, and that is the
  # order rule above rather than a preference. `catalog-votes-consumer` sorts before `media` and
  # `moderation`, so an alphabetical merge would renumber the metric ids of every domain after it
  # on every apply that touched the consumer list. Appending pins the consumers behind the domains
  # instead, so a new consumer takes the next free id and disturbs nothing.
  #
  # Appending pins the consumers behind the domains, but it does not pin them against each other:
  # the consumer half is itself sorted, so a new consumer whose name sorts before an existing one
  # renumbers that one. Row 28 is the first to hit this. `catalog-part-purge-consumer` sorts
  # between `admin-price-alerts-consumer` and `catalog-votes-consumer`, so it takes m8 and pushes
  # `catalog-votes-consumer` from m8 to m9, and both aggregate alarms have that term rewritten.
  # Like the domain case below it is expected rather than drift.
  #
  # A new domain is the other case that renumbers, and row 26 was the first to hit it. Domains
  # come first in the concat, so `build-lists` took m5, which `catalog-votes-consumer` had held
  # since row 24, and pushed that consumer to m6. Both aggregate alarms have the consumer's term
  # rewritten as a result. That is inside the four alarm changes a cut already expects rather than
  # extra plan noise, because both alarms change anyway for their descriptions and for the term the
  # new function appends. Row 27 does the same one slot further along: `identity` takes m6, which
  # `admin-price-alerts-consumer` held after row 25, and pushes both consumers back a place, to m7
  # and m8. Rows 29 and 31 each repeat it, so a renumbered consumer term in one of those plans is
  # expected and is not drift.
  alarm_lambda_function_names = concat(
    [
      for name in local.lambda_domain_names : module.lambda_domain[name].function_name
      if contains(keys(local.lambda_domains), name)
    ],
    [
      for name in sort(keys(local.lambda_stream_consumers)) :
      module.lambda_stream_consumer[name].function_name
    ],
  )

  # The log groups the error metric filters read: the monolith's, plus one per created domain
  # function, the same shape and the same source as the fail open list below. A metric filter is
  # created against a named log group that must already exist, so this keys off
  # `local.lambda_domains` and not off the nine names.
  #
  # The stream consumer's group is in here too. Its handler logs through the same
  # app/core/logging.py JsonFormatter every domain function uses, so the { $.level = "ERROR" }
  # filter reads it unchanged, and a consumer that cannot write a part logs exactly the kind of
  # handled error this alarm exists to catch: the invocation itself succeeds, having reported the
  # record as a batch item failure, so AWS/Lambda Errors stays at zero and only the log says
  # anything went wrong.
  #
  # The keys are prefixed so a consumer can never collide with a domain of the same name. Nothing
  # collides today, and the filters are named from these keys, so a silent overwrite here would be
  # a metric filter quietly missing rather than a plan error.
  alarm_error_log_groups = merge(
    { api = module.lambda_api.log_group_name },
    { for name in keys(local.lambda_domains) : name => module.lambda_domain[name].log_group_name },
    {
      for name in keys(local.lambda_stream_consumers) :
      "consumer-${name}" => module.lambda_stream_consumer[name].log_group_name
    },
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
  #
  # `lambda_aggregate_alarm` is the list being non-empty rather than a bare true, because the
  # module validates the pair: "lambda_aggregate_alarm = true needs at least one name in
  # lambda_function_names". In every environment that has cut a domain this is true and nothing
  # about the alarms changes. In a fresh account applying with `bootstrap_image_tag = ""` there is
  # no domain function yet, so the aggregate pair is simply not created, and it arrives with the
  # second apply alongside the functions it sums. The alternative, passing `true` unconditionally,
  # is a variable validation error on the first apply of every new account, which is exactly the
  # class of knowingly failing apply this gate exists to remove.
  lambda_function_names      = local.alarm_lambda_function_names
  lambda_aggregate_alarm     = length(local.alarm_lambda_function_names) > 0
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
  # across all of them and has no metric math ceiling to run into as rows 29 and 31 add the
  # remaining two log groups.
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
  #
  # Row 24's consumer group is in the shared list and is the one group here where the filter can
  # never match: a stream consumer builds no application, installs no middleware and has no caller
  # to limit. It is left in rather than filtered out because a metric filter that matches nothing
  # costs nothing and adds no metric data, while diverging the two lists to exclude it would trade
  # that for a second list to keep correct. If a later row gives a consumer something the limiter
  # touches, the group is already here.
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
