# ---------------------------------------------------------------------------
# Stream consumers. Split plan row 24, and the first of them.
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
# **The seam this closes.** Section 1.3's seam 3. `VoteService` used to write
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
# **Why this is a function and not a second handler on `catalog`.** A Lambda
# function has one handler. `catalog` runs uvicorn under the Web Adapter, and an
# event source mapping has no way to reach a second entry point inside that
# process. Two functions off one image is both the shape AWS supports and the
# better one: the consumer gets its own concurrency, timeout, IAM policy and
# error rate, so a vote storm cannot take request capacity from the catalog
# routes and a consumer bug does not page as a catalog API error.
# ---------------------------------------------------------------------------

locals {
  # The one consumer this row cuts, held as a map so rows 25 and 28 through 30
  # add a key rather than copy the four resources below. Keyed by the function
  # name suffix, which is what makes `carmodpicker-<env>-catalog-votes-consumer`
  # and keeps the ECR repository it borrows from explicit.
  #
  # `image_repository` is the domain whose image this function runs, and
  # `command` is what makes one image serve two functions. The image is built
  # once with DOMAIN=catalog and declares a CMD that starts the HTTP entrypoint;
  # Lambda's image_config.command overrides that CMD, so the same digest runs
  # the consumer module instead. That is what keeps the two functions from
  # skewing: one build, one push, one digest, and the deploy that updates
  # `catalog` updates this function with the same bytes.
  #
  # `stream_table` is both the table whose stream is read and the key into
  # `aws_sqs_queue.stream_dlq`, so a mapping cannot be pointed at one table's
  # stream and another table's dead letter queue.
  lambda_stream_consumers_declared = {
    catalog-votes-consumer = {
      image_repository = "catalog"
      stream_table     = "votes"
      command          = ["app.entrypoints.catalog_votes_consumer.handler"]

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
    for name, consumer in local.lambda_stream_consumers : name => {
      DEBUG                 = "false"
      APP_ENVIRONMENT       = var.environment
      DYNAMODB_TABLE_PREFIX = local.prefix

      WEBBPULSE_OTEL_SAMPLE_RATIO        = var.environment == "production" ? "0.1" : "1.0"
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"
    }
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

  # The one thing that differs from a domain function. The image's own CMD
  # starts the HTTP entrypoint out of /etc/carmodpicker-entrypoint; this
  # replaces it with the Lambda handler string, which the runtime interface
  # client in the base image resolves to the module attribute of the same name.
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

  # LATEST rather than TRIM_HORIZON, which is the decision that says this row
  # needs no backfill. TRIM_HORIZON would replay up to 24 hours of vote records
  # at the moment of the apply, and every one of them would recompute a part
  # whose aggregate the old inline write had already set correctly. The recount
  # is idempotent so that would be harmless, but it would be a burst of writes
  # to buy nothing. The aggregate is correct at cutover because the synchronous
  # write and this consumer compute the identical number, `upvotes - downvotes`,
  # so there is no window where the column is wrong and nothing to catch up on.

  batch_size = 100

  # Up to five seconds of buffering before a partial batch is delivered. The
  # aggregate is eventually consistent by design now, and the vote routes carry
  # the authoritative counts in their own response, so nothing a user sees is
  # waiting on this. Five seconds buys real batching on a part that is being
  # voted on quickly, where it collapses many records into one recount.
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

  # Two retries, then the destination. The handler's own failures are DynamoDB
  # throttles and timeouts, which either clear in seconds or are not going to
  # clear at all, and the mapping's exponential backoff means two attempts
  # already spans that. A larger number trades a stalled shard for a slightly
  # better chance on a transient error, which is the wrong trade when the
  # destination preserves the record for a human either way.
  maximum_retry_attempts = 2

  # A record older than an hour is not worth retrying. The aggregate is
  # recomputed from current state, so a stale record's recount produces the same
  # answer a newer record's would; holding the shard for it buys nothing.
  maximum_record_age_in_seconds = 3600

  # The contract the handler implements. Without it the mapping reads the
  # function's return value as nothing and retries the entire batch on any
  # error, which is what turns one unwritable part into repeated writes on every
  # other part in the batch.
  function_response_types = ["ReportBatchItemFailures"]

  # Where a batch goes when the retries are spent. Row 22 created exactly this
  # queue per streamed table for exactly this purpose. What lands here is the
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
