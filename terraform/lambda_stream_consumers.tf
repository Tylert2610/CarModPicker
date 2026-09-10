# ---------------------------------------------------------------------------
# Stream consumers. Split plan rows 24 and 25.
#
# Row 22 turned on four DynamoDB streams and created a dead letter queue for
# each, and deliberately created no consumer: "the consumers are Lambda event
# source mappings that arrive with the seams in rows 24 and 25". This file is
# that arrival. It holds the functions that read a stream rather than serve
# HTTP, which is why they are here and not in lambda_domains.tf: a domain
# function in that file is an HTTP surface behind the Lambda Web Adapter with a
# route cut in apigateway.tf, and none of that is true of anything declared
# here.
#
# **The seams these close.** Section 1.3's seam 3, and now seam 4 alongside it.
#
# Seam 3. `VoteService` used to write
# `parts.net_votes` inline on every vote, which is the `moderation` domain
# writing a table `catalog` owns, and it is why `moderation` carries `parts` in
# its write list today. The consumer below inverts that: `moderation` writes
# only `votes`, the stream carries the change to a function `catalog` owns, and
# that function recomputes the aggregate and writes the part. The narrowing of
# `moderation`'s grant is in lambda_domains.tf and is the other half of this
# row; the two have to land together, because a grant removed before the
# consumer exists leaves the aggregate with nothing writing it and a consumer
# added before the grant is removed leaves two writers racing.
#
# Seam 4. `part_listing_service` used to call `evaluate_alerts_for_listing`
# inline at the end of every price capture, which is `catalog` reading `admin`'s
# alert rows and calling SES on the request thread. The second consumer inverts
# that: `catalog` writes only its own listing, the `part_listings` stream carries
# the change to a function `admin` owns, and that function evaluates the alerts
# and sends the mail. Its two halves land together for the same reason: the
# consumer without the removal of the inline call sends every alert twice, and
# the removal without the consumer sends none at all.
#
# **Why these are functions and not routes on `catalog` and `admin`.** The consumer is a web
# application, same as every other function here: the base image ships the
# Lambda Web Adapter and no runtime interface client, so the adapter is the
# runtime. For a trigger that is not HTTP the adapter POSTs the raw event JSON
# to AWS_LWA_PASS_THROUGH_PATH and returns the app's response body as the
# function result, which is the documented shape for DynamoDB streams. So a
# route on the existing domain function would in fact work. It is still the
# wrong answer: an event source mapping's concurrency, timeout and error rate
# would then be shared with that domain's API, a vote storm or a crawler run
# would take request capacity from the routes users are waiting on, and a
# consumer bug would page as an API error. A separate function off the same
# image keeps one build, one digest and one deploy while giving the consumer its
# own concurrency, its own timeout, its own IAM policy and its own error metric.
#
# The IAM half of that is not decorative on row 25. `admin`'s price alerts
# consumer holds `ses:SendEmail`; the `admin` HTTP function does not, and must
# not, because no route it serves sends mail. Folding the consumer into it would
# put a send grant behind twelve authenticated routes to buy nothing.
# ---------------------------------------------------------------------------

locals {
  # The consumers, held as a map so rows 28 through 30 add a key rather than copy
  # the four resources below, which is exactly what row 25 did. Keyed by the
  # function name suffix, which is what makes
  # `carmodpicker-<env>-catalog-votes-consumer` and
  # `carmodpicker-<env>-admin-price-alerts-consumer` and keeps the ECR repository
  # each borrows from explicit.
  #
  # `image_repository` is the domain whose image this function runs, and
  # `command` is what makes one image serve two functions. The image is built
  # once with DOMAIN=<that domain> and its CMD starts the module named in
  # /etc/carmodpicker-entrypoint; Lambda's image_config.command overrides that
  # CMD to start this module instead. Both are `python -m <module>` starting a
  # uvicorn server, because both run under the Web Adapter. That is what keeps
  # the two functions from skewing: one build, one push, one digest, and the
  # deploy that updates `catalog` updates this function with the same bytes.
  #
  # `stream_table` is both the table whose stream is read and the key into
  # `aws_sqs_queue.stream_dlq`, so a mapping cannot be pointed at one table's
  # stream and another table's dead letter queue.
  #
  # `work_queue` names a key in `local.work_queues` when the consumer also
  # drains one, and is null when it does not. Row 28 is the first to set it, and
  # it is what gives that function a second event source mapping on top of the
  # stream one every consumer here gets. It is spelled out as null on the two
  # stream only consumers rather than omitted, because every entry in this map
  # must carry the same attributes: Terraform reads a map whose entries differ in
  # shape as an object, and the `domain_functions_enabled` gate below then fails
  # to type-check against `{}`.
  lambda_stream_consumers_declared = {
    catalog-votes-consumer = {
      image_repository = "catalog"
      stream_table     = "votes"
      command          = ["python", "-m", "app.entrypoints.catalog_votes_consumer"]

      # Stream only. Explicitly null rather than omitted: every entry in this map
      # has to carry the same attributes or the `domain_functions_enabled` gate
      # below stops type-checking against `{}`, because a map whose entries differ
      # in shape is an object rather than a map.
      work_queue = null

      # 256 MB, matching `catalog` itself. The work per invoke is a Query for
      # the vote counts and an UpdateItem per distinct part in the batch, with
      # no image handling and nothing native anywhere in the path.
      memory = 256

      # 60 seconds. Unlike a domain function there is no 29 second API Gateway
      # integration timeout overhead here, so the ceiling is chosen from the
      # work: a full batch is at most `batch_size` records, which collapse to at
      # most that many distinct parts, each costing one Query and one
      # conditional UpdateItem. 60 seconds is roughly two orders of magnitude of
      # headroom over that, which matters because a timeout is retried as a
      # whole batch and a batch that times out repeatedly is how a stream shard
      # stalls.
      timeout = 60

      # No secrets and no S3. The consumer verifies no token and serves no
      # request, so it needs neither SECRET_KEY nor the images bucket. This is
      # the narrowest runtime policy of any function in the estate and it should
      # stay that way.
      secrets = false

      # `parts` is written and `votes` is read, which is the seam stated as a
      # policy. Note the direction against `moderation`'s: that domain now reads
      # nothing of `parts` and writes `votes`, and this function is the mirror.
      tables      = ["parts"]
      read_tables = ["votes"]

      # No mail. Row 25's consumer below is the one that sends, and this row's
      # does not, which is why the flag exists rather than the grant being
      # unconditional.
      ses = false
    }

    # Split plan row 25, section 1.3's seam 4. `part_listing_service` used to
    # call `evaluate_alerts_for_listing` inline, on the request thread, right
    # after the price transaction committed: a fan-out read of
    # `part_price_alerts`, `parts`, `retailers` and `users` plus an SES send,
    # all inside a 29 second Lambda, on a write a user was waiting on. Three of
    # those tables and the send belong to `admin`. This function is the
    # inversion: `admin` reads the `part_listings` stream and owns the alert
    # rows and the mail, and `catalog` loses the SES grant it should never have
    # had. The other half of the row is the removal of the synchronous call in
    # backend/app/api/services/part_listing_service.py, and the two land
    # together for the reason row 24's two halves did: the consumer without the
    # removal sends every alert twice, and the removal without the consumer
    # sends none at all.
    admin-price-alerts-consumer = {
      image_repository = "admin"
      stream_table     = "part_listings"
      command          = ["python", "-m", "app.entrypoints.admin_price_alerts_consumer"]

      # Stream only, explicitly null. See the note on the votes consumer above.
      work_queue = null

      # 256 MB, matching `admin` itself. The work per invoke is a Query on the
      # alerts index, two GetItems, and one GetItem plus one UpdateItem per
      # firing alert, with an HTTPS call to SES between them. Nothing native and
      # no image handling anywhere in the path.
      memory = 256

      # 60 seconds, the same reasoning as the votes consumer with one addition:
      # the work here includes a synchronous SES call per firing alert, and SES
      # is the one dependency in this path that is not DynamoDB. A listing whose
      # part has many subscribers is the long case, and the batching window plus
      # the per-listing collapse below keep a batch to at most `batch_size`
      # listings rather than that many observations.
      timeout = 60

      # Unlike the votes consumer, this one reads the app secret. The alert
      # email carries a one-click unsubscribe link, which is a 30 day JWT signed
      # with SECRET_KEY, so `send_price_drop_alert_email` reaches
      # `create_access_token`. Without the grant the send would fail per alert
      # inside the evaluation's own exception handling, where the only symptom
      # is a warning and a user who never hears about a price drop.
      secrets = true

      # The grant lambda_domains.tf's `admin` entry deliberately does not carry,
      # arriving here with the code that uses it. Section 3.4 always put
      # `admin`'s half of the SES split on the price drop alert; row 21 refused
      # to configure it on a function serving no route that sends, and this is
      # that row. The `admin` HTTP function still gets neither the grant nor
      # EMAIL_FROM, and its descriptor in app/composition/domains.py is
      # unchanged.
      ses = true

      # `part_price_alerts` is written, because a send stamps `last_fired_at`,
      # which is the marker that makes a redelivered record idempotent. The
      # other three are read: `parts` and `retailers` for the email body, and
      # `users` for the address to send it to. `retailers` is the one table
      # row 21 left out of `admin`'s grant on the grounds that no admin route
      # reached it, and the reach it named was exactly this evaluation, so the
      # grant arrives with the handler as that row said it would.
      #
      # `part_listings` is not in either list. Its stream is the trigger and the
      # record carries the whole item, so the consumer never reads the table
      # back, and the stream grant below is on the stream ARN rather than the
      # table's.
      tables      = ["part_price_alerts"]
      read_tables = ["parts", "retailers", "users"]
    }

    # Split plan row 28, section 1.3's seam 2. `purge_related_rows_for_parts`
    # used to run inline at the end of every part delete, deleting rows in
    # `build_list_parts`, `votes`, `reports` and `part_price_alerts`, four
    # tables owned by `build-lists`, `moderation` twice and `admin`. This
    # function is the inversion: the delete writes a tombstone and returns, the
    # `parts` stream carries it here, and this function performs the cascade.
    #
    # It is the first consumer with two event source mappings. The stream
    # mapping below turns a tombstone into a message on the `part-purge` work
    # queue; the queue mapping drains that queue and does the deletes. The queue
    # sits in the middle because a stream record lives 24 hours and a mapping's
    # retries are spent in minutes, while a queue message lives four days, is
    # retried five times, and reaches a dead letter queue carrying the part id
    # rather than the shard and sequence range a stream failure preserves. Row
    # 22 created that queue for exactly this and the plan names it for seam 2.
    #
    # One function rather than two, because both halves share this image, this
    # bundle and these grants; a second function would be a second cold start, a
    # second log group and a second slot against the alarm chunk ceiling of ten,
    # in exchange for a split the logs already make.
    catalog-part-purge-consumer = {
      image_repository = "catalog"
      stream_table     = "parts"
      work_queue       = "part-purge"
      command          = ["python", "-m", "app.entrypoints.catalog_part_purge_consumer"]

      # 256 MB, matching `catalog` itself and both consumers above. The work per
      # invoke is a Query and a BatchWriteItem per table in the cascade, with no
      # image handling and nothing native in the path.
      memory = 256

      # 29 seconds, and this is the one consumer whose timeout is not 60. It is
      # pinned to `local.work_queue_consumer_timeout` in sqs.tf, which is what
      # the `part-purge` queue's visibility timeout of 174 was derived from as
      # six times that number. Lambda refuses an SQS event source mapping whose
      # function timeout exceeds the queue's visibility timeout, and raising
      # this to 60 without also raising the queue would fail the apply, while
      # raising the queue would move it for row 30's `user-delete` queue too.
      # 29 is ample: the cascade is four Queries and at most four
      # BatchWriteItems for one part.
      #
      # No batch window is set on the queue mapping below for the same reason.
      # sqs.tf notes that a batch window would require the visibility timeout to
      # rise by that many seconds beyond the six times multiple, and not setting
      # one keeps 174 exactly correct rather than approximately so.
      timeout = 29

      # No secrets and no mail. The cascade signs no token and sends nothing; it
      # deletes rows. This is the same narrow shape as the votes consumer and
      # unlike row 25's, which needed SECRET_KEY to sign an unsubscribe link.
      secrets = false
      ses     = false

      # The four tables of the cascade, all written. This is the seam stated as
      # a policy: these are the tables `catalog` was reaching into from the
      # request path, and they are now reached only from this function.
      #
      # `parts` is deliberately absent from both lists. The stream is the
      # trigger and the record carries the tombstoned image, so the consumer
      # never reads the part back, and it never writes one: the hard delete and
      # the unique label release both stay in `PartService.purge`, synchronously,
      # because a part that reads as deleted while still holding its GTIN
      # reservation would block a software engineer from re creating it.
      tables      = ["build_list_parts", "votes", "reports", "part_price_alerts"]
      read_tables = []
    }
  }

  # Gated on exactly the condition the domain functions are gated on, and for
  # exactly the same reason: this function is created from an image, Lambda
  # pulls that image at CreateFunction, and in a fresh account the repository it
  # borrows does not exist until this root's first apply. It also genuinely
  # depends on that repository being populated, because it runs `catalog`'s
  # image rather than one of its own.
  lambda_stream_consumers = local.domain_functions_enabled ? local.lambda_stream_consumers_declared : {}

  # Same shape as `local.lambda_domain_write_arns` and its read twin in
  # lambda_domains.tf, including the `/index/*` wildcard: the vote count is a
  # Query against the votes table's entity index, and a Query naming an index is
  # authorized against the index ARN rather than the table's.
  lambda_stream_consumer_write_arns = {
    for name, consumer in local.lambda_stream_consumers : name => flatten([
      for table in consumer.tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_stream_consumer_read_arns = {
    for name, consumer in local.lambda_stream_consumers : name => flatten([
      for table in consumer.read_tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  # The domain environment, minus the keys a consumer has no use for. CORS and
  # the frontend URL are HTTP concerns and this function answers no request;
  # naming them would be a misleading configuration in the console, which is the
  # same argument lambda_domains.tf makes for leaving EMAIL_FROM off a function
  # that sends no mail.
  #
  # The rate limits table is left out for the same reason. The limiter is
  # middleware on an application this function does not build, and a stream
  # consumer has no caller to rate limit.
  lambda_stream_consumer_environment = {
    for name, consumer in local.lambda_stream_consumers : name => merge({
      DEBUG                 = "false"
      APP_ENVIRONMENT       = var.environment
      DYNAMODB_TABLE_PREFIX = local.prefix

      WEBBPULSE_OTEL_SAMPLE_RATIO        = var.environment == "production" ? "0.1" : "1.0"
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"

      # The adapter's pass-through contract, both halves of it, set explicitly
      # so the whole thing is readable in a plan rather than half implied by a
      # default and half missing.
      #
      # The path is where the adapter POSTs a non-HTTP event payload. "/events"
      # is already the default, but it is also the route the entrypoint declares
      # and the string its tests pin, and a silent disagreement between the two
      # is the worst failure available here: the adapter would POST to a path
      # FastAPI answers 404 on, the adapter would hand that 404 back as a
      # successful invoke, and the mapping would ack every record it just failed
      # to process. Written down, the plan shows the contract.
      AWS_LWA_PASS_THROUGH_PATH = "/events"

      # The status codes the adapter reports to Lambda as a function error.
      # This one is not a default: without it the adapter returns a 500 response
      # body as a *successful* invoke, which would ack the batch and lose it.
      # With it, an unhandled exception in the consumer surfaces as a real
      # function error, so the mapping bisects, retries, and eventually routes
      # the batch to the stream dead letter queue, which is exactly the row 22
      # failure path this function is meant to inherit.
      AWS_LWA_ERROR_STATUS_CODES = "500-599"
      },
      # The work queue URL, and only on a consumer that drains one. The producer
      # half of row 28's consumer sends with a URL rather than an ARN, which is
      # why outputs.tf publishes both. `app/consumers/part_purge.py` raises when
      # it is unset rather than defaulting, so a misconfiguration fails the
      # invoke instead of acking a batch it never enqueued.
      consumer.work_queue != null ? {
        PART_PURGE_QUEUE_URL = aws_sqs_queue.work[consumer.work_queue].id
      } : {},
      # The sender, and only on a consumer that sends. `app/core/email.py` reads
      # EMAIL_FROM for the SES `FromEmailAddress` and EMAIL_ENABLED as the
      # switch that turns `_send` from a debug log into a call, so both are
      # needed and neither is on a function without ses:SendEmail. Setting them
      # on the votes consumer would be configuration for a code path that cannot
      # execute, which is the same argument lambda_domains.tf's header makes
      # about the monolith's environment map.
      consumer.ses ? {
        EMAIL_FROM    = local.email_from
        EMAIL_ENABLED = "true"

        # The part link in the email body. `app/core/email.py` builds it from
        # `settings.frontend_base_url`, which falls back to a hostname derived
        # from APP_ENVIRONMENT when this is unset, and that fallback is how
        # staging once mailed production links. Every domain function sets it
        # for the same reason; a function that composes an email needs it more
        # than most.
        #
        # API_URL is deliberately not set, matching the nine domain functions.
        # `settings.api_base_url` derives the unsubscribe link's origin from
        # APP_ENVIRONMENT, which is correct in both environments, and adding a
        # key here that no domain function carries would be this file's first
        # divergence from that map rather than a fix for anything.
        FRONTEND_URL = local.frontend_url

        # The app secret's ARN, which is what `secrets = true` above grants and
        # what config.py's lazy resolution reads SECRET_KEY out of. The
        # unsubscribe token is signed with it.
        APP_SECRETS_ARN = module.app_secrets.arns["app"]
    } : {})
  }
}

module "lambda_stream_consumer" {
  for_each = local.lambda_stream_consumers

  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 2.1"

  # `carmodpicker-<env>-catalog-votes-consumer`. The prefix plus the map key,
  # the same shape module.lambda_domain uses, which is what lets the deploy
  # role's existing grant on `carmodpicker-<env>-*` reach it and what the image
  # map in deploy-backend.yml builds to name it for UpdateFunctionCode.
  function_name = "${local.prefix}-${each.key}"
  role_name     = "${local.prefix}-lambda-${each.key}"

  package_type = "Image"

  # The one thing that differs from a domain function. The image's own CMD reads
  # /etc/carmodpicker-entrypoint and starts that module; this replaces it with a
  # direct `python -m` of the consumer module. Not a Lambda handler string:
  # there is no runtime interface client in this image, so a handler string
  # would be exec'd as a file of that literal name and the container would not
  # start. What starts is uvicorn, and the Web Adapter extension in
  # /opt/extensions polls the Runtime API and forwards each invoke to it.
  image_config = {
    command = each.value.command
  }

  architectures = ["arm64"]
  memory_size   = each.value.memory
  timeout       = each.value.timeout

  # Borrowed, not its own. The repository URL comes from module.registry keyed
  # by the *image's* domain rather than by this function's name, which is what
  # keeps the estate at nine repositories rather than ten and what guarantees
  # this function and `catalog` run the same bytes.
  code = {
    image_uri = "${module.registry.repository_urls[each.value.image_repository]}:${var.bootstrap_image_tag}"
  }

  environment_variables = local.lambda_stream_consumer_environment[each.key]

  log_retention_days           = 7
  log_format                   = "JSON"
  application_log_level        = "INFO"
  system_log_level             = "INFO"
  set_logging_config_log_group = true

  tracing_mode             = "Active"
  attach_xray_write_policy = true

  tags = { Name = "${local.prefix}-${each.key}" }
}

# ---------------------------------------------------------------------------
# The runtime policy. Same four building blocks as a domain function's, plus the
# two a stream consumer needs and a domain function does not: reading the stream
# and writing the failure destination.
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_stream_consumer" {
  for_each = local.lambda_stream_consumers

  name = "${each.key}-runtime"
  role = module.lambda_stream_consumer[each.key].role_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "WriteOwnLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${module.lambda_stream_consumer[each.key].log_group_arn}:*"
        },
        {
          Sid      = "WriteSpansToTheXRayOTLPEndpoint"
          Effect   = "Allow"
          Action   = ["xray:PutSpans", "xray:PutSpansForIndexing"]
          Resource = "*"
        },
        # The four actions an event source mapping's poller needs, and no more.
        # They are granted on the stream ARN rather than the table's, because a
        # stream is its own resource: the table ARN would authorize nothing here
        # and the stream ARN authorizes no table operation, which is what keeps
        # this statement from widening the DynamoDB grants below.
        #
        # ListStreams takes no resource-level permission and is the one action
        # of the four that has to be "*".
        {
          Sid    = "ReadTheTableStream"
          Effect = "Allow"
          Action = [
            "dynamodb:DescribeStream",
            "dynamodb:GetRecords",
            "dynamodb:GetShardIterator",
          ]
          Resource = [module.dynamodb.stream_arns[each.value.stream_table]]
        },
        {
          Sid      = "ListStreams"
          Effect   = "Allow"
          Action   = ["dynamodb:ListStreams"]
          Resource = "*"
        },
        # The on_failure destination. The mapping writes the failed batch's
        # metadata here on the poller's behalf using the *function's* role, so
        # without this grant the destination silently drops the record and the
        # dead letter queue stays empty while batches are being discarded, which
        # is the worst of both outcomes.
        {
          Sid      = "WriteFailedBatchesToTheDeadLetterQueue"
          Effect   = "Allow"
          Action   = ["sqs:SendMessage"]
          Resource = [aws_sqs_queue.stream_dlq[each.value.stream_table].arn]
        },
      ],
      # The work queue, both ends of it, and only for a consumer that has one.
      # Row 28's function is both the producer and the drainer, so it needs
      # SendMessage for the stream half and the three poller actions for the
      # queue half. They are one statement because they are one queue and one
      # function; splitting them would suggest the two halves could be granted
      # apart, and they cannot be while one function serves both mappings.
      #
      # GetQueueAttributes is required by the event source mapping rather than
      # by the handler: the poller reads the queue's attributes when it starts
      # and the mapping fails to enable without it.
      each.value.work_queue != null ? [
        {
          Sid    = "DrainAndFeedTheWorkQueue"
          Effect = "Allow"
          Action = [
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
          ]
          Resource = [aws_sqs_queue.work[each.value.work_queue].arn]
        },
      ] : [],
      length(local.lambda_stream_consumer_write_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadWriteOwnTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_write_actions
          Resource = local.lambda_stream_consumer_write_arns[each.key]
        },
      ] : [],
      length(local.lambda_stream_consumer_read_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadSharedTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_read_actions
          Resource = local.lambda_stream_consumer_read_arns[each.key]
        },
      ] : [],
      each.value.secrets ? [
        {
          Sid      = "ReadTheAppSecret"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = [module.app_secrets.arns["app"]]
        },
      ] : [],
      # Section 3.4's SES split, `admin`'s half of it, arriving with the handler
      # that sends. The two resources are the same pair the monolith's
      # `data.aws_iam_policy_document.ses_send` names in lambda.tf, and they are
      # both required rather than either: SESv2 `SendEmail` authorizes against
      # the sending identity and, because `app/core/email.py` passes
      # `ConfigurationSetName`, against the configuration set as well. Naming
      # only one of them fails the send with an AccessDenied that reads as if
      # the other were missing.
      #
      # `identity/*` rather than a single identity ARN, which is the one place
      # this is wider than it looks and is deliberate. `local.custom_domain`
      # decides whether the verified identity is the domain
      # (`identity/staging.carmodpicker.com`) or the bare sender mailbox
      # (`identity/no-reply@...`), the two are different resources created by
      # different `aws_sesv2_email_identity` blocks under mutually exclusive
      # counts, and a policy naming the one that does not exist in this
      # environment breaks the send. The wildcard is scoped to this account and
      # this region by the ARN itself, and the account holds one SES identity,
      # so what it actually widens to is nothing. Narrowing it to the active
      # identity is worth doing when the two identity resources are unified,
      # and that is a change to ses.tf rather than to this file.
      #
      # SendRawEmail is not granted. The monolith carries it because its policy
      # predates the SESv2 client; `_send` calls `sesv2:SendEmail` and nothing
      # in this image composes a raw MIME message.
      each.value.ses ? [
        {
          Sid    = "SendTransactionalMail"
          Effect = "Allow"
          Action = ["ses:SendEmail"]
          Resource = [
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*",
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.transactional.configuration_set_name}",
          ]
        },
      ] : [],
    )
  })
}

# ---------------------------------------------------------------------------
# The event source mapping. Every setting below is a failure-handling decision,
# because the defaults for a DynamoDB stream mapping are the ones that stall a
# shard.
#
# A stream shard is ordered, and a failing batch blocks it. The default
# `maximum_retry_attempts` is -1, which means retry until the record expires
# from the stream, so one poison record with the default settings stops every
# later record on that shard for 24 hours. The three settings that prevent that
# are bisect on error, a finite retry count, and a failure destination, and all
# three are set here.
# ---------------------------------------------------------------------------

resource "aws_lambda_event_source_mapping" "stream_consumer" {
  for_each = local.lambda_stream_consumers

  event_source_arn  = module.dynamodb.stream_arns[each.value.stream_table]
  function_name     = module.lambda_stream_consumer[each.key].function_arn
  starting_position = "LATEST"

  # LATEST rather than TRIM_HORIZON, which is the decision that says neither row
  # needs a backfill, and on row 25's mapping it is load bearing rather than
  # merely tidy. TRIM_HORIZON on `part_listings` would replay up to 24 hours of
  # listing writes at the moment of the apply, and every price drop among them
  # would be evaluated as if it had just happened: a day of alert emails, all at
  # once, for drops the synchronous evaluation had already mailed about before
  # the apply. The 24 hour cooldown marker would suppress the ones that fired
  # inside the window and nothing would suppress the rest. On row 24's mapping
  # the same setting is a cost decision rather than a correctness one, because a
  # replayed recount is idempotent.

  batch_size = 100

  # Up to five seconds of buffering before a partial batch is delivered. Nothing
  # a user is looking at waits on either consumer: the vote routes carry the
  # authoritative counts in their own response, and a price alert is an email
  # whose latency budget is minutes rather than seconds. Five seconds buys real
  # batching on an entity being written to quickly, where it collapses many
  # records into one recount or one evaluation.
  maximum_batching_window_in_seconds = 5

  # Halve the batch and retry each half when the function errors on a batch. It
  # is what isolates one bad record from the good ones around it: without it a
  # single failing record fails its whole batch on every retry, and all hundred
  # records land on the dead letter queue together.
  #
  # The handler also reports partial batch failures, below, which is the finer
  # grained mechanism and the one that does the work in the normal case. Bisect
  # is the backstop for the case that mechanism cannot cover: a function that
  # times out or runs out of memory returns no response at all, so there is no
  # list of failures to read and the whole batch is retried. Bisecting is what
  # then narrows it.
  bisect_batch_on_function_error = true

  # Two retries, then the destination. A handler's own failures are DynamoDB
  # throttles and timeouts, which either clear in seconds or are not going to
  # clear at all, and the mapping's exponential backoff means two attempts
  # already spans that. A larger number trades a stalled shard for a slightly
  # better chance on a transient error, which is the wrong trade when the
  # destination preserves the record for a human either way. Two is also the
  # right ceiling for a handler whose side effect is an email: a retry of a
  # partially completed evaluation can duplicate a send that the cooldown marker
  # had not yet been written for, so fewer retries is fewer chances at that.
  maximum_retry_attempts = 2

  # A record older than an hour is not worth retrying. For the vote aggregate,
  # because it is recomputed from current state and a stale record's recount
  # produces the same answer a newer one's would. For a price alert, because an
  # email about a price that moved more than an hour ago is worth less than the
  # shard it would hold, and a later observation on the same listing carries a
  # current price to alert on instead.
  maximum_record_age_in_seconds = 3600

  # The contract the handler implements. Without it the mapping reads the
  # function's return value as nothing and retries the entire batch on any
  # error, which is what turns one unwritable part into repeated writes on every
  # other part in the batch.
  function_response_types = ["ReportBatchItemFailures"]

  # Where a batch goes when the retries are spent, keyed by the streamed table
  # so a mapping can only ever fail into its own table's queue. Row 22 created
  # exactly this queue per streamed table for exactly this purpose. What lands here is the
  # failure metadata and the shard and sequence range, not the records
  # themselves, which is enough to find them on the stream while it retains
  # them and enough to alarm on.
  destination_config {
    on_failure {
      destination_arn = aws_sqs_queue.stream_dlq[each.value.stream_table].arn
    }
  }

  depends_on = [aws_iam_role_policy.lambda_stream_consumer]
}

# ---------------------------------------------------------------------------
# The work queue mapping, for a consumer that drains one. Row 28's is the first
# and today the only one.
#
# It is a separate resource rather than another instance of the mapping above
# because almost none of the settings carry over. An SQS mapping has no shard
# and therefore no ordering to stall, no starting position, no record age, and
# no on_failure destination: the queue's own redrive policy is the failure path,
# which is the durability the work queue was chosen for in the first place.
# ---------------------------------------------------------------------------

resource "aws_lambda_event_source_mapping" "work_queue_consumer" {
  for_each = {
    for name, consumer in local.lambda_stream_consumers : name => consumer
    if consumer.work_queue != null
  }

  event_source_arn = aws_sqs_queue.work[each.value.work_queue].arn
  function_name    = module.lambda_stream_consumer[each.key].function_arn

  # Ten rather than the hundred the stream mapping uses. An SQS batch is not
  # ordered and its failure unit is the message, so a big batch buys less here
  # than it does on a stream, and it costs more when things go wrong: every
  # message in a batch shares one visibility timeout, so a batch of a hundred
  # cascades has to finish inside 29 seconds or the whole batch becomes visible
  # again while the function is still working on it. Ten cascades is four
  # Queries and up to four BatchWriteItems each, which fits that window with
  # room to spare.
  batch_size = 10

  # No maximum_batching_window_in_seconds, deliberately. sqs.tf derives the
  # queue's visibility timeout as six times the consumer timeout and notes that
  # a batch window requires adding that window on top. Leaving it unset keeps
  # the existing 174 exactly right rather than approximately right, and there is
  # nothing to gain: a purge is not latency sensitive, but it is also not
  # frequent enough for batching to save meaningful invocations.

  # The same contract the stream mapping implements, keyed by messageId rather
  # than by sequence number. Without it a single failed cascade returns the
  # whole batch to the queue, so nine successful cascades would be re-run. They
  # are idempotent, so that would be correct but wasteful; more importantly it
  # would drive the successful messages toward maxReceiveCount and eventually
  # move messages to the dead letter queue that had never failed.
  function_response_types = ["ReportBatchItemFailures"]

  # Two batches in flight at most. The cascade is a delete fan out and there is
  # no reason to let a burst of purges scale this function against the same
  # tables the API is serving; the queue is what absorbs the burst instead. It
  # also keeps the function well inside the account concurrency the HTTP
  # functions share.
  scaling_config {
    maximum_concurrency = 2
  }

  depends_on = [aws_iam_role_policy.lambda_stream_consumer]
}
