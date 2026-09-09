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
# state and puts the platform's 7 day retention on it.
#
# Why this is gated rather than unconditional. An import block whose target does
# not exist is a plan time error, not a skipped no-op, so an unconditional import
# means the very first apply in a fresh account fails at plan: the destination
# flip and the import would be in the same run, and X-Ray has not written a span
# yet, so there is nothing to adopt. That ordering is not something the
# configuration can fix, because the group's existence depends on traffic rather
# than on Terraform.
#
# So `adopt_spans_log_group` is the operator saying "the group exists in this
# account now". It defaults to true, which is the state of every environment that
# has already been through this, so nothing changes for staging or for production
# once they are past it. A fresh account applies once with it false, generates a
# span, then sets it true and applies again. See the Promoting to a fresh account
# section of docs/migration/split-plan.md.
#
# for_each on an import block, matched by for_each on the resource, rather than
# `count`: an import block's `to` must address the same instance key the resource
# uses, and a `for_each` over a set of at most one string gives both a stable
# instance address of ["aws/spans"] that does not renumber. It is available from
# Terraform 1.7, and both workspaces are well past that (staging resolves
# `~> 1.10` to 1.16.1, production is pinned at 1.14.8), so required_version
# does not move.
locals {
  spans_log_groups = var.adopt_spans_log_group ? toset(["aws/spans"]) : toset([])
}

variable "adopt_spans_log_group" {
  description = "Adopt the reserved aws/spans log group into state and hold it at the platform's 7 day retention. X-Ray creates that group itself the first time it writes a span to the CloudWatchLogs destination, and it cannot be created ahead of time because CreateLogGroup rejects names beginning with aws/. An import block whose target does not exist is a plan time error, so a brand new account has to apply once with this false, generate one span, and then set it true. true is correct for every environment where a span has already been written, which is both of ours."
  type        = bool
  default     = true
}

# Adding for_each renames the state address from aws_cloudwatch_log_group.spans
# to aws_cloudwatch_log_group.spans["aws/spans"], and without this block that
# rename reads as a destroy and a create. Deleting the group would throw away
# every span already written and the create would then fail on the reserved
# name, so the refactor has to be a move rather than a replace. This is what
# makes the change a no-op in staging, where the group is already in state.
#
# The block stays after the group is adopted everywhere. A moved block whose
# source is not in state is a no-op, and removing it later would break any
# environment that had not yet planned under this version.
moved {
  from = aws_cloudwatch_log_group.spans
  to   = aws_cloudwatch_log_group.spans["aws/spans"]
}

import {
  for_each = local.spans_log_groups

  to = aws_cloudwatch_log_group.spans[each.key]
  id = each.value
}

resource "aws_cloudwatch_log_group" "spans" {
  for_each = local.spans_log_groups

  name              = each.value
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
