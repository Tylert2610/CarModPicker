data "aws_iam_policy_document" "ses_send" {
  statement {
    actions = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = [
      "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*",
      "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.transactional.configuration_set_name}",
    ]
  }
}

data "aws_iam_policy_document" "user_images_rw" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:HeadObject",
    ]
    resources = ["${aws_s3_bucket.user_images.arn}/*"]
  }

  statement {
    actions   = ["s3:ListBucket", "s3:HeadBucket"]
    resources = [aws_s3_bucket.user_images.arn]
  }
}

# The shared rate limiter's grant, layer 2 of the rate limiting standard.
#
# The wildcard statement below already covers `<prefix>-rate-limits`, so this adds no
# effective permission today. It is written separately and scoped to the one table,
# with only the four actions the limiter actually calls, because the per-domain split
# replaces that wildcard with per-function policies: at that point every domain needs
# the limiter grant and no domain should inherit read/write on every other domain's
# tables to get it. Having the narrow statement already named and tested means the
# split moves a known-good block rather than deriving a new one under time pressure.
#
# DescribeTable is deliberately absent. The limiter never calls it, and a limiter that
# fails open has no reason to probe the table's existence.
data "aws_iam_policy_document" "dynamodb_rate_limits_rw" {
  statement {
    sid = "SharedRateLimiterCounters"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
    ]

    resources = [module.dynamodb.table_arns["rate-limits"]]
  }
}

data "aws_iam_policy_document" "dynamodb_tables_rw" {
  statement {
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:ConditionCheckItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:UpdateItem",
    ]
    resources = [
      "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${local.prefix}-*",
      "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${local.prefix}-*/index/*",
    ]
  }
}

data "aws_iam_policy_document" "lambda_api_runtime" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.app_secrets.arns["app"]]
  }

  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${module.lambda_api.log_group_arn}:*"]
  }

  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_api_dynamodb" {
  name   = "dynamodb-tables"
  role   = module.lambda_api.role_id
  policy = data.aws_iam_policy_document.dynamodb_tables_rw.json
}

resource "aws_iam_role_policy" "lambda_api_rate_limits" {
  name   = "dynamodb-rate-limits"
  role   = module.lambda_api.role_id
  policy = data.aws_iam_policy_document.dynamodb_rate_limits_rw.json
}

resource "aws_iam_role_policy" "lambda_api_ses" {
  name   = "ses-send"
  role   = module.lambda_api.role_id
  policy = data.aws_iam_policy_document.ses_send.json
}

resource "aws_iam_role_policy" "lambda_api_s3" {
  name   = "s3-user-images"
  role   = module.lambda_api.role_id
  policy = data.aws_iam_policy_document.user_images_rw.json
}

resource "aws_iam_role_policy" "lambda_api_runtime" {
  name   = "runtime"
  role   = module.lambda_api.role_id
  policy = data.aws_iam_policy_document.lambda_api_runtime.json
}

data "archive_file" "lambda_placeholder" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_placeholder"
  output_path = "${path.module}/.terraform/lambda_placeholder.zip"
}

locals {
  lambda_environment = { for key, value in {
    DEBUG                 = "false"
    APP_ENVIRONMENT       = var.environment
    PORT                  = "8000"
    USER_IMAGES_BUCKET    = aws_s3_bucket.user_images.bucket
    S3_ENDPOINT_URL       = ""
    EMAIL_FROM            = local.email_from
    EMAIL_ENABLED         = "true"
    SENTRY_RELEASE        = var.sentry_release
    SENTRY_SERVICE_NAME   = "lambda-api"
    AWS_EMF_ENVIRONMENT   = "Local"
    RUN_STARTUP_TASKS     = "false"
    DYNAMODB_TABLE_PREFIX = local.prefix
    # Layer 2 of the rate limiting standard. The name is passed explicitly rather than
    # left to the prefix convention so the function and the table cannot drift to
    # different names, and so a plan error rather than a runtime fail-open is what
    # surfaces if the table is ever renamed or re-keyed.
    RATE_LIMITS_TABLE = module.dynamodb.table_names["rate-limits"]
    APP_SECRETS_ARN   = module.app_secrets.arns["app"]
    FRONTEND_URL      = local.frontend_url
    ALLOWED_ORIGINS   = local.allowed_origins
  } : key => value if value != "" }
}

module "lambda_api" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 1.6"

  # 1.8 attaches its own inline xray-write policy whenever tracing is Active. The runtime policy
  # below already grants xray:PutTraceSegments and xray:PutTelemetryRecords, so the module's copy
  # would be redundant and this adoption stays a zero diff. Cleanup for a later pass: drop the
  # X-Ray statement from data.aws_iam_policy_document.lambda_api_runtime and let this default back
  # to true, so the module that turns tracing on also owns the grant.
  attach_xray_write_policy = false

  function_name = "${local.prefix}-api"
  role_name     = "${local.prefix}-lambda-api"

  runtime       = "python3.13"
  handler       = "app.lambda_handler.handler"
  architectures = ["x86_64"]
  memory_size   = 1024
  timeout       = 29

  code = {
    filename         = data.archive_file.lambda_placeholder.output_path
    source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256
  }

  environment_variables = local.lambda_environment

  log_retention_days    = 7
  log_format            = "JSON"
  application_log_level = "INFO"
  system_log_level      = "INFO"

  tags = { Name = "${local.prefix}-api" }
}
