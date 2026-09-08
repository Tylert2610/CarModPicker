# ---------------------------------------------------------------------------
# CloudWatch Transaction Search.
#
# Why this exists. The platform migration settled on OpenTelemetry to X-Ray with
# no collector, so each domain function exports OTLP over HTTP straight to the
# X-Ray OTLP endpoint, https://xray.us-west-2.amazonaws.com/v1/traces. AWS makes
# Transaction Search a prerequisite for that endpoint: "If you are using traces,
# make sure Transaction Search is enabled to send spans to the X-Ray OTLP
# endpoint." The domain carve-outs in section 5 of the split plan wire the
# functions to the endpoint and wait on this file. Without it the functions
# export to an endpoint that will not accept the spans.
#
# What it changes, and it is worth reading before applying. Transaction Search is
# account-wide for the region, not per environment or per function, so this
# switches trace storage for everything in the account that writes segments, not
# only the CarModPicker functions. Spans stop being stored as X-Ray traces and are
# written as structured logs to the aws/spans log group instead, which puts them
# on CloudWatch Logs pricing. The indexing rule below keeps 1 percent of
# traceIds indexed for trace summaries, which is the free tier and the AWS
# default.
#
# On destroy. Neither aws_xray_trace_segment_destination nor
# aws_xray_indexing_rule reverts anything in AWS when it is removed. The provider
# documents both with the same note: "Removing this resource from Terraform has
# no effect on the [destination configuration / indexing rule] within AWS X-Ray."
# Both adopt an account singleton rather than creating a new object, so a destroy
# leaves the destination on CloudWatchLogs and the Default rule at whatever
# percentage was last applied. Reverting is an explicit change of `destination`
# back to "XRay", not a `terraform destroy`.
# ---------------------------------------------------------------------------

# Lets X-Ray put spans into the two log groups Transaction Search writes to. The
# source conditions are the confused deputy guard from the AWS setup docs: they
# hold X-Ray to this account's own resources when it assumes the service
# principal.
data "aws_iam_policy_document" "transaction_search_spans" {
  statement {
    sid    = "TransactionSearchAccess"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["xray.amazonaws.com"]
    }

    actions = ["logs:PutLogEvents"]

    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:aws/spans:*",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/application-signals/data:*",
    ]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:xray:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "transaction_search_spans" {
  policy_name     = "${local.prefix}-transaction-search-spans"
  policy_document = data.aws_iam_policy_document.transaction_search_spans.json
}

# The switch itself. Depends on the resource policy so the destination never
# flips before X-Ray is allowed to write.
resource "aws_xray_trace_segment_destination" "main" {
  destination = "CloudWatchLogs"

  depends_on = [aws_cloudwatch_log_resource_policy.transaction_search_spans]
}

# X-Ray creates the aws/spans log group itself the first time it writes to the
# CloudWatchLogs destination. It cannot be created ahead of time: CreateLogGroup
# rejects the name with "Log groups starting with AWS/ are reserved for AWS".
# Step one (the destination above) applied on staging on 2026-09-08 and X-Ray
# created the group with its own 30 day default, so step two adopts it into
# state and puts the platform's 7 day retention on it. The import block is a
# no-op once the group is in state and stays here so a fresh environment
# converges in one apply after X-Ray has created the group.
import {
  to = aws_cloudwatch_log_group.spans
  id = "aws/spans"
}

resource "aws_cloudwatch_log_group" "spans" {
  name              = "aws/spans"
  retention_in_days = 7

  depends_on = [aws_xray_trace_segment_destination.main]
}

# Adopts the account's existing "Default" indexing rule rather than creating a
# new named one: the provider's own example uses name = "Default" and imports by
# that name. 1 percent is the AWS default and the free tier. Raising it indexes
# more traceIds for trace summaries and starts costing money. The account's rule
# currently reads 0 percent, so the first apply raises it to the default.
resource "aws_xray_indexing_rule" "default" {
  name = "Default"

  rule {
    probabilistic {
      desired_sampling_percentage = 1
    }
  }

  depends_on = [aws_xray_trace_segment_destination.main]
}
