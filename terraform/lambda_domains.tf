# ---------------------------------------------------------------------------
# The per-domain FastAPI functions, delivered as container images and run under
# the AWS Lambda Web Adapter. Section 3.3 and section 3.4 of
# docs/migration/split-plan.md, row 13 of section 8.
#
# `media` from row 13 and `build-logs` from row 18 are the entries today. Rows
# 19 through 31 add the other seven, one per row, and the shape here is built
# for that: everything a domain needs is one entry in `local.lambda_domains`,
# and the module call, the IAM policy and the outputs all key off it, so adding
# a domain is adding a map entry.
#
# The monolith in lambda.tf is deliberately untouched. It still serves every
# route this file has not cut away from it, because a function here is only
# reached once apigateway.tf names its prefixes. That is what keeps each row
# additive and its rollback a matter of deleting the route entry again.
#
# Every AWS_LWA_* setting is baked into the image by backend/Dockerfile
# (AWS_LWA_PORT, AWS_LWA_READINESS_CHECK_PATH, AWS_LWA_READINESS_CHECK_PROTOCOL
# and AWS_LWA_ASYNC_INIT), and so is PORT, and so is RUN_STARTUP_TASKS. None is
# repeated here. Repeating one would put two sources of truth on the same
# setting and let them drift, and PORT is the one where drift is fatal rather
# than untidy: the monolith's environment sets PORT=8000 while the image binds
# and polls 8080, so copying the monolith's map wholesale would present as a
# readiness check that never passes with no application logs to say why.
# ---------------------------------------------------------------------------

locals {
  # One entry per domain whose function exists. The keys are names from
  # `local.lambda_domain_names` in ecr.tf, which is what ties a function to its
  # ECR repository and to the deploy role's grant.
  #
  # `secrets` is whether the function reads the carmodpicker-<env>/app secret at
  # all; `tables` names the tables it writes and `read_tables` the ones it only
  # reads, both as keys of module.dynamodb, so every ARN comes out of the module
  # rather than being rebuilt by hand and a renamed table is a plan error rather
  # than a runtime denial.
  #
  # How `media`'s two table lists were derived, from the code rather than from
  # the plan's ownership column:
  #
  #   - `app/composition/domains.py` declares `_MEDIA_REPOSITORIES` as `users`,
  #     `car_generations`, `parts`, `build_lists` and `image_source_mappings`.
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those five
  #     repository names to a table suffix, and for `media` the mapping is the
  #     identity: the five repositories are the five tables.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph and fails if it drifts, so the bundle is
  #     the checked statement of what this function can reach.
  #   - Of the five, only `image_source_mappings` is written.
  #     `app/api/endpoints/images.py` calls `repos.image_source_mappings.record`
  #     and `.get_by_source_url`, and reaches the other four through `.get` and
  #     through `app/api/utils/bucket_orphan_utils.py`'s orphan sweep, which is
  #     five full reads to find unreferenced S3 objects. Section 1.2's ownership
  #     table agrees: `image_source_mappings` is owned by `media` and written by
  #     nothing else, and `media` appears in no other row's "also written today
  #     by" column. So `media` is the one domain whose write set needs no seam
  #     unwound before it is cut, which is part of why it is cut first.
  #   - `rate-limits` is in `tables` and is not in either of those lists. It is
  #     the shared limiter's counter table, layer 2 of the rate limiting
  #     standard, and it is reached from the middleware stack rather than from a
  #     repository, so `_MEDIA_REPOSITORIES` cannot name it. Every one of the
  #     nine gets it, for the reason locals in lambda.tf already records: the
  #     per-domain split replaces the monolith's wildcard with per-function
  #     policies, and at that point every domain needs the limiter grant. The
  #     limiter fails open, so withholding it would not break the function; it
  #     would silently turn layer 2 off for this domain and log a warning on
  #     every request, which is worse than a denial because nothing fails.
  #
  # `s3` is whether the function gets the user images bucket. Only `media` and,
  # from row 31, `users` do; section 3.4 gives `users` the three object actions
  # for avatars and `media` the full set including ListBucket.
  # How `build-logs`'s two table lists were derived, by row 18 and by the same
  # method as `media`'s above, from the code rather than from the ownership
  # column:
  #
  #   - `app/composition/domains.py` declares `_BUILD_LOGS_REPOSITORIES` as
  #     `users`, `build_lists`, `build_logs` and `build_log_posts`, and
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those four to a
  #     table suffix of the same name, so the four repositories are four tables.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph, so the bundle is a checked statement
  #     of what this function can reach.
  #   - Of the four, only `build_log_posts` is written. The domain has five
  #     routes and `app/api/endpoints/build_logs.py` calls `.create`, `.update`
  #     and `.delete` on `repos.build_log_posts` alone; `build_logs`,
  #     `build_lists` and `users` are reached through `.get`, `.get_many`,
  #     `.for_build_list`, `.all_for_build_log` and `.count`, every one a read.
  #   - `build_logs` is in `read_tables` even though section 1.2 gives this
  #     domain ownership of it, and that is deliberate rather than an oversight.
  #     Ownership is about who may write a table, not about who does today, and
  #     nothing in this domain's own five routes writes it: the thread row is
  #     created by `app/api/services/build_list_service.py` when a build list is
  #     created and deleted by `build_log_delete_actions` in the same cascade,
  #     both of which run in `build-lists` and are seam work for row 26. Until
  #     that seam moves, granting this function write on `build_logs` would
  #     grant an action no code path here takes, which is the opposite of what
  #     a per-domain split is for. Row 26 is where the grant follows the writer.
  #   - `rate-limits` is in `tables` for the reason `media`'s entry above
  #     records: it is the shared limiter's counter table, reached from the
  #     middleware stack rather than from a repository, so the bundle cannot
  #     name it, and the limiter fails open, so withholding it would silently
  #     turn layer 2 off for this domain rather than failing.
  #
  # 256 MB rather than `media`'s 512. `media` is sized for Pillow decoding
  # uploaded images in memory; this domain serves five JSON routes over
  # DynamoDB with no image handling and no native work, so it takes the smaller
  # size. It is also the cheapest thing to raise if the cold start or the
  # duration says otherwise, since memory is the only tuning knob on a function
  # this simple.
  lambda_domains = {
    media = {
      secrets     = true
      s3          = true
      memory      = 512
      tables      = ["image_source_mappings", "rate-limits"]
      read_tables = ["users", "car_generations", "parts", "build_lists"]
    }
    build-logs = {
      secrets     = true
      s3          = false
      memory      = 256
      tables      = ["build_log_posts", "rate-limits"]
      read_tables = ["users", "build_lists", "build_logs"]
    }
  }

  # DynamoDB actions a domain gets on a table it writes. The same twelve the
  # monolith's runtime policy carries, so a domain moving off the monolith
  # cannot lose an action it was relying on.
  dynamodb_domain_write_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem",
    "dynamodb:ConditionCheckItem",
    "dynamodb:DeleteItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:TransactGetItems",
    "dynamodb:TransactWriteItems",
    "dynamodb:UpdateItem",
  ]

  # And on a table it only reads. Five, as section 3.4 says.
  # TransactGetItems and ConditionCheckItem are left out on purpose: nothing in
  # a read only path uses them, and including them would blur the line the least
  # privilege claim rests on.
  dynamodb_domain_read_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
  ]

  # Table and index ARNs per domain, resolved through module.dynamodb. The
  # /index/* wildcard is on both sets because a Query naming an index is
  # authorized against the index ARN and not the table's: `media` reads `parts`
  # and `build_lists` through their owner indexes in the orphan sweep, and
  # `image_source_mappings` carries its own.
  lambda_domain_write_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_domain_read_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.read_tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  # What every domain function is told about itself and its environment. The
  # monolith's `local.lambda_environment` in lambda.tf is the reference, minus
  # the four keys a domain function must not or need not carry:
  #
  #   - PORT and RUN_STARTUP_TASKS are baked into the image; see the file header.
  #   - EMAIL_FROM and EMAIL_ENABLED are `identity`'s and `admin`'s, per
  #     section 3.4's SES split. `media` sends no mail, and a configured sender
  #     on a function with no ses:SendEmail grant is a misleading configuration.
  #   - SENTRY_SERVICE_NAME is gone. Row 16 removed `init_sentry` from every
  #     entrypoint, so nothing in a domain function reads it, and a Sentry
  #     variable on a function with no Sentry in it is a misleading
  #     configuration. The monolith in lambda.tf keeps its own until row 31.
  #
  # The two OTEL_ variables are the whole tracing contract, and they are what
  # row 16 turns on. `webbpulse.otel.configure_tracing` builds the pipeline
  # itself rather than running under `opentelemetry-instrument`, so
  # OTEL_EXPORTER_OTLP_TRACES_PROTOCOL, OTEL_PYTHON_DISTRO,
  # OTEL_PYTHON_CONFIGURATOR and OTEL_TRACES_SAMPLER are deliberately not set:
  # the protocol is implicit in the exporter class the package constructs, the
  # distribution is used as a library rather than a launcher, and the sampler is
  # passed explicitly so a ratio sampler in the environment cannot pre-drop the
  # spans the tail step exists to judge.
  #
  # WEBBPULSE_OTEL_SAMPLE_RATIO is the probability a *non-error* trace is kept.
  # Errors are kept whatever it says, which is the point of tail sampling and is
  # why 0.1 on production is not the 90 percent loss of failures a head sampler
  # at the same ratio would be. Staging keeps everything, because its traffic is
  # this repository's own tests and a smoke run.
  #
  # The endpoint is what un-gates the code. `configure_tracing` in
  # app/composition/wiring.py returns early unless it is set, which is what
  # keeps the test suite and a local run free of an exporter, so setting it here
  # is what makes tracing a Terraform change rather than a code change.
  lambda_domain_environment = {
    for name, domain in local.lambda_domains : name => merge(
      {
        DEBUG                 = "false"
        APP_ENVIRONMENT       = var.environment
        DYNAMODB_TABLE_PREFIX = local.prefix

        # Named explicitly rather than left to the prefix convention, for the
        # same reason lambda.tf names it: the function and the table cannot
        # drift to different names, and a plan error rather than a runtime
        # fail open is what surfaces if the table is ever renamed.
        RATE_LIMITS_TABLE = module.dynamodb.table_names["rate-limits"]

        FRONTEND_URL    = local.frontend_url
        ALLOWED_ORIGINS = local.allowed_origins

        AWS_EMF_ENVIRONMENT = "Local"

        WEBBPULSE_OTEL_SAMPLE_RATIO = var.environment == "production" ? "0.1" : "1.0"
        # Set explicitly rather than left to the package's own default, which
        # derives the same URL from AWS_REGION. Naming it here is what makes the
        # destination visible in the plan and in the console, so a function
        # exporting nowhere is a diff rather than an archaeology exercise.
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"
      },
      domain.secrets ? { APP_SECRETS_ARN = module.app_secrets.arns["app"] } : {},
      domain.s3 ? {
        USER_IMAGES_BUCKET = aws_s3_bucket.user_images.bucket
        # Empty means "the real S3 endpoint". The monolith filters empty values
        # out of its map for this key; here it is simply not set, which is the
        # same thing to pydantic and one fewer moving part.
      } : {},
    )
  }
}

variable "bootstrap_image_tag" {
  description = "Image tag used as the seed for every per-domain function, as pushed to ECR by the container image build in deploy-backend.yml. Lambda pulls and optimises the image when it creates the function, so a tag that does not resolve fails the create: the tag named here must already exist in the repository of every domain in local.lambda_domains before the apply. It is only ever a seed, because image_uri is on the lambda-function module's ignore_changes list, so the deploy step's UpdateFunctionCode is not undone by the next plan and this value never needs changing again."
  type        = string

  validation {
    condition     = can(regex("^sha-[0-9a-f]{40}$", var.bootstrap_image_tag))
    error_message = "bootstrap_image_tag must be sha- followed by a full 40 character commit sha, which is the tag the container image build pushes."
  }
}

module "lambda_domain" {
  for_each = local.lambda_domains

  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 2.1"

  # `carmodpicker-<env>-<domain>`, which is exactly the key the image map in
  # .github/workflows/deploy-backend.yml builds for UpdateFunctionCode and the
  # name pattern the deploy role's lambda_domain_function_arns already grants
  # on. Changing this shape breaks both without a plan error.
  function_name = "${local.prefix}-${each.key}"
  role_name     = "${local.prefix}-lambda-${each.key}"

  # An Image function takes neither runtime nor handler: the image supplies
  # both, and the module rejects either one alongside package_type = "Image".
  # No image_config either, because the Dockerfile already declares the CMD that
  # starts this domain's entrypoint out of /etc/carmodpicker-entrypoint.
  package_type = "Image"

  # arm64, per section 2.6, which is where the monolith's x86_64 is left behind.
  # Row 11 verified the three native pins on aarch64 (Pillow, bcrypt, webauthn)
  # by building and running all nine images, and `media` is the one that
  # exercises Pillow, which is why the plan cuts it first.
  architectures = ["arm64"]
  memory_size   = each.value.memory

  # 29 seconds, matching the HTTP API integration timeout the routes in row 14
  # will use. A longer function timeout is invisible because the gateway gives
  # up first.
  timeout = 29

  # The seed only. The repository URL comes from module.registry rather than
  # being rebuilt from the account id and the region, so the function and the
  # repository cannot drift to different names.
  code = {
    image_uri = "${module.registry.repository_urls[each.key]}:${var.bootstrap_image_tag}"
  }

  environment_variables = local.lambda_domain_environment[each.key]

  # 7 days, the retention the platform migration decision settled on, and
  # created by Terraform rather than lazily by Lambda so the retention is in
  # place from the first invoke instead of after the group has already collected
  # a run of never expiring events. The monolith stays at 14 until row 17 moves
  # both; this function starts where it is going to end up.
  log_retention_days           = 7
  log_format                   = "JSON"
  application_log_level        = "INFO"
  system_log_level             = "INFO"
  set_logging_config_log_group = true

  # Unlike the monolith, whose runtime policy carried the two X-Ray actions
  # before the module owned them, these roles are new, so the module attaches
  # its own X-Ray write policy and the runtime policy below does not repeat
  # xray:PutTraceSegments or xray:PutTelemetryRecords. It does add
  # xray:PutSpans, which the module's policy does not carry; see the statement
  # below.
  tracing_mode             = "Active"
  attach_xray_write_policy = true

  tags = { Name = "${local.prefix}-${each.key}" }
}

# ---------------------------------------------------------------------------
# One runtime policy per domain, naming only that domain's tables. Section 3.4.
#
# Logs are here, because the module creates the log group but leaves writing to
# it to the application, the same way the monolith's runtime policy does.
#
# X-Ray is here only in part, and row 16 is what put it here. The module's
# attach_xray_write_policy grants xray:PutTraceSegments and
# xray:PutTelemetryRecords, which are the two actions the X-Ray *segment* API
# takes and the two the Lambda service itself needs for Active tracing, so those
# are not repeated. They are not the actions the OTLP endpoint takes:
# `POST https://xray.<region>.amazonaws.com/v1/traces` is authorized by
# xray:PutSpans, and that is the call webbpulse's OTLPAwsSpanExporter makes on
# every flush. Neither the module's inline policy nor the AWS managed
# AWSXrayWriteOnlyAccess carries it, so without the statement below every export
# is a 403, which the exporter retries in silence, and the symptom is that
# traces never appear with nothing in the logs to say why.
#
# xray:PutSpansForIndexing is granted alongside it. Both actions are in the
# X-Ray service authorization reference at Write level, and the pair is what
# Transaction Search indexes a span through; PutSpans alone would export the
# span and leave it unsearchable. Neither action takes a resource-level
# permission, so "*" is the only resource either accepts.
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_domain" {
  for_each = local.lambda_domains

  name = "${each.key}-runtime"
  role = module.lambda_domain[each.key].role_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "WriteOwnLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${module.lambda_domain[each.key].log_group_arn}:*"
        },
        {
          Sid      = "WriteSpansToTheXRayOTLPEndpoint"
          Effect   = "Allow"
          Action   = ["xray:PutSpans", "xray:PutSpansForIndexing"]
          Resource = "*"
        },
      ],
      length(local.lambda_domain_write_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadWriteOwnTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_write_actions
          Resource = local.lambda_domain_write_arns[each.key]
        },
      ] : [],
      length(local.lambda_domain_read_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadSharedTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_read_actions
          Resource = local.lambda_domain_read_arns[each.key]
        },
      ] : [],
      # The one app secret, and only for the domains that read it. `media`'s
      # descriptor in app/composition/domains.py declares
      # requires_secrets=("SECRET_KEY",), because all eight of its routes verify
      # a token, and SECRET_KEY is a key of the carmodpicker-<env>/app JSON.
      #
      # Written out rather than taken from module.app_secrets.read_policy_statement,
      # which Portfolio uses, because that output's policy_actions default is the
      # pair GetSecretValue and DescribeSecret. Section 3.4 names one action and
      # the monolith's runtime policy grants one action, so this grants one
      # action. The resource still comes off the module, so the policy cannot
      # name a secret the module does not create.
      each.value.secrets ? [
        {
          Sid      = "ReadTheAppSecret"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = [module.app_secrets.arns["app"]]
        },
      ] : [],
      # The user images bucket. The object actions and the bucket action are two
      # statements because they take different resources: an object action is
      # authorized against `<bucket>/*` and ListBucket against the bucket ARN
      # itself, so folding them together would grant neither what it needs.
      #
      # Section 3.4 lists five actions here and this grants four, and the
      # difference is a correction rather than a reduction. `s3:HeadObject` is
      # not an IAM action: it does not appear in AWS's own machine readable
      # service reference for S3, and the HeadObject API is authorized by
      # `s3:GetObject`, which is already granted above. IAM accepts an action
      # name that matches nothing without complaint, so the monolith's policy in
      # lambda.tf carries both `s3:HeadObject` and `s3:HeadBucket` today and
      # neither has ever granted anything; only Access Analyzer's advisory
      # ValidatePolicy flags them, and nothing in the pipeline runs it. Carrying
      # them forward would make this policy look broader than it is, which is
      # the opposite of what a per-domain split is for. Cleanup for a later
      # pass: drop the same two from the monolith's user_images_rw document.
      #
      # `s3:ListBucket` is doing two jobs. It authorizes list_objects_v2, which
      # the orphan sweep pages through, and it is also what authorizes
      # head_bucket, the call StorageService.__init__ makes once per cold start
      # to decide whether uploads are enabled at all. Without it the service
      # disables itself silently and every upload route answers as if the bucket
      # were unconfigured, with a warning in the logs and no error to the caller.
      each.value.s3 ? [
        {
          Sid    = "ReadWriteUserImageObjects"
          Effect = "Allow"
          Action = [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
          ]
          Resource = ["${aws_s3_bucket.user_images.arn}/*"]
        },
        {
          Sid      = "ListTheUserImagesBucket"
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [aws_s3_bucket.user_images.arn]
        },
      ] : [],
    )
  })
}
