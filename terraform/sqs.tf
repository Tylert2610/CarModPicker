# ---------------------------------------------------------------------------
# Event plumbing for the seams, split plan row 22 and section 7.
#
# Two different things live here and they are not interchangeable. Both carry a
# dead letter queue, which is why they share a file, but what feeds them and what
# drains them is different.
#
# 1. Stream consumer dead letter queues, one per streamed table. These are not
#    work queues and nothing sends to them directly. A DynamoDB stream is read by
#    a Lambda event source mapping, and there is no path from a stream to a queue
#    without a consumer in between: an event source mapping targets a Lambda
#    function and nothing else. What lands here is a batch the consumer could not
#    process, written by the mapping's on_failure destination once the retries
#    configured on the mapping are spent.
#
#    The mappings and their consumer functions arrive with the seams in rows 24
#    and 25. This row creates the queues first so the mapping that names one has
#    something to point at, and because a destination that does not exist is an
#    apply time failure rather than a plan time one.
#
#    Note what an on_failure record actually holds: metadata about the failed
#    batch and the shard position it came from, not the stream records. A
#    responder draining one of these re-reads the stream at that position, which
#    only works inside the stream's own 24 hour retention. That is the window,
#    and it is why the depth alarm below is on a short period.
#
# 2. Work queues for the two seams that are genuinely asynchronous jobs rather
#    than stream reactions, the part purge in row 28 and the user delete cascade
#    in row 30. A tombstone write is followed by a fan out of deletes across
#    several domains, and each of those is a unit of work with its own retry and
#    its own failure mode. Each work queue has its own dead letter queue and a
#    redrive policy, which is the part that matters: a cleanup handler that fails
#    repeatedly must not silently drop a delete, because the visible symptom is a
#    user who deleted their account and whose build lists are still public.
#
# Every queue here is a standard queue. Ordering is not a property any of this
# needs: DynamoDB streams already guarantee order per item, and the cleanup
# handlers are idempotent by construction because deleting a row that is already
# gone is a no op in DynamoDB. A FIFO queue would buy ordering nothing needs and
# cost the throughput ceiling and the dead letter queue caveats that come with it.
# ---------------------------------------------------------------------------

locals {
  # The streams whose consumers need somewhere to put a batch they could not
  # process. Keyed by table so a queue name reads as the table it belongs to, and
  # derived from the same map that turns the streams on in dynamodb.tf rather than
  # relisted here, so a fifth streamed table cannot arrive without its queue.
  stream_consumer_dlqs = keys(local.dynamodb_stream_view_types)

  # The asynchronous jobs, and the consumer timeout each one is sized for.
  #
  # Neither consumer exists yet, so the timeout is an assumption rather than a
  # reading, and it is written down because the visibility timeout is derived from
  # it. Both are assumed to run at the same 29 seconds every domain function uses
  # (lambda_domains.tf), which is the ceiling the HTTP API integration timeout
  # sets and the value a handler moved out of a request path inherits.
  #
  # AWS recommends a visibility timeout of at least six times the function
  # timeout, so that a batch being retried after a throttle is not handed to a
  # second consumer while the first still holds it:
  # https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html
  # Six times 29 is 174. If a consumer is later given a longer timeout, this has
  # to move with it, and Lambda refuses an event source mapping whose function
  # timeout exceeds the queue's visibility timeout, so the failure is loud.
  #
  # One refinement for whoever writes the consumers: with a batch window, the
  # recommendation becomes six times the function timeout plus
  # MaximumBatchingWindowInSeconds. A consumer that sets a batch window has to
  # raise this by that many seconds rather than leaving it at 174.
  work_queue_consumer_timeout = 29

  work_queues = {
    part-purge = {
      description = "Seam 2, split plan row 28. Fan out of deletes after a part is tombstoned, drained by build-lists, moderation and admin."
    }
    user-delete = {
      description = "Seam 1, split plan row 30. Fan out of deletes after a user is tombstoned, drained by every domain that owns a table the cascade touches."
    }
  }
}

# ---------------------------------------------------------------------------
# Stream consumer dead letter queues, one per streamed table.
# ---------------------------------------------------------------------------

resource "aws_sqs_queue" "stream_dlq" {
  for_each = toset(local.stream_consumer_dlqs)

  name = "${local.prefix}-${replace(each.key, "_", "-")}-stream-dlq"

  # SSE-SQS rather than SSE-KMS. It is AES-256 at rest at no additional cost and
  # with no key policy to maintain, and nothing here crosses an account boundary
  # or needs a customer managed key for an audit. SSE-KMS would add a per request
  # KMS charge and a grant on every consumer role for no property this needs.
  #
  # Set explicitly rather than relied on as a default: the default only applies to
  # a queue created without encryption attributes, and Terraform always sends
  # them.
  # https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-server-side-encryption.html
  sqs_managed_sse_enabled = true

  # 14 days, the SQS maximum. A failed batch here is a bug someone has to look at,
  # and the useful window is however long it takes a person to notice and respond.
  # The default of 4 days can expire a failure that arrived on a Friday before
  # anyone reads it.
  message_retention_seconds = 1209600

  # No redrive policy. This queue is already the end of the line: it is where an
  # event source mapping's on_failure destination writes, not a queue a consumer
  # polls, so there is no receive count to act on.

  tags = { Name = "${local.prefix}-${replace(each.key, "_", "-")}-stream-dlq" }
}

# ---------------------------------------------------------------------------
# Work queues for the two asynchronous seams, each with its own dead letter queue.
# ---------------------------------------------------------------------------

resource "aws_sqs_queue" "work_dlq" {
  for_each = local.work_queues

  name                    = "${local.prefix}-${each.key}-dlq"
  sqs_managed_sse_enabled = true

  # Longer than the source queue's retention, and deliberately so. A standard
  # queue keeps a message's original enqueue timestamp when it moves to a dead
  # letter queue, so a message that spent time in the source queue arrives here
  # having already used part of its life. AWS states the rule directly: always set
  # the dead letter queue's retention longer than the source queue's.
  # https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
  message_retention_seconds = 1209600

  tags = { Name = "${local.prefix}-${each.key}-dlq" }
}

resource "aws_sqs_queue" "work" {
  for_each = local.work_queues

  name                    = "${local.prefix}-${each.key}"
  sqs_managed_sse_enabled = true

  # 4 days, the SQS default, and shorter than the dead letter queue's 14 above so
  # the pair follows the rule in that comment. A delete that has not been applied
  # in four days is not going to be applied by waiting longer; it needs the
  # attention that reaching the dead letter queue is meant to trigger.
  message_retention_seconds = 345600

  # Six times the assumed 29 second consumer timeout. See the note on
  # work_queue_consumer_timeout above for why this number is derived rather than
  # chosen, and what has to change if a consumer is given a longer timeout.
  visibility_timeout_seconds = local.work_queue_consumer_timeout * 6

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.work_dlq[each.key].arn

    # Five attempts before a message is moved aside. AWS recommends at least five
    # for a Lambda consumer, which gives the function a few chances to retry
    # before a message goes to the dead letter queue, and it is the right end of
    # the range here because the retries this absorbs are throttles and timeouts
    # rather than genuinely poisoned messages: the handlers are idempotent, so a
    # retry is free, and a delete that is dropped is worse than one that is tried
    # twice.
    # https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html
    maxReceiveCount = 5
  })

  tags = { Name = "${local.prefix}-${each.key}" }
}

# ---------------------------------------------------------------------------
# One aggregate dead letter queue depth alarm over all six queues.
#
# One alarm, not six. This is the same house rule the DynamoDB throttle alarm
# follows in monitoring.tf, and for the same two reasons: six alarms is six
# subscriptions and twelve billable alarm metrics to say one thing, and the thing
# worth paging on is "a cleanup handler is dropping work", which is true whichever
# queue it happened on. The alarm names the queue in its description so the
# responder still knows where to look, and the queue dimension is on each metric,
# so the alarm history says which term fired.
#
# The metric math is the same shape the api-alarms module builds for its aggregate
# alarms: one metric per queue with return_data false, and one expression summing
# them that returns the data the alarm evaluates. Six terms is well under the 10
# metric ceiling that makes the module chunk its Lambda alarms, so this stays one
# alarm for the life of the migration.
#
# ApproximateNumberOfMessagesVisible rather than NumberOfMessagesSent: depth is
# the condition worth alarming on. A message that arrived and was drained by a
# responder should stop paging once it is gone, and a queue that is not empty is
# the state that needs attention regardless of when the message landed. Maximum
# rather than Sum over the period, because the statistic is already a gauge; Sum
# would multiply one stuck message by the number of samples in the period.
# ---------------------------------------------------------------------------

locals {
  # Every dead letter queue in one ordered list, the four stream queues first and
  # then the two work queues, each paired with the name that goes in the metric
  # label. Order is load bearing in the same way the alarm module's function list
  # is: the expression names metric ids positionally, so reordering this rewrites
  # the expression on an existing alarm.
  dlq_alarm_queues = concat(
    [for key in sort(local.stream_consumer_dlqs) : aws_sqs_queue.stream_dlq[key].name],
    [for key in sort(keys(local.work_queues)) : aws_sqs_queue.work_dlq[key].name],
  )
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name        = "${local.prefix}-dlq-depth"
  alarm_description = "Messages waiting in any of the ${length(local.dlq_alarm_queues)} dead letter queues: ${join(", ", local.dlq_alarm_queues)}. A non empty dead letter queue means a stream consumer or a cleanup handler gave up on work it was given, so a delete or a price alert has been dropped rather than applied."

  # Any message at all. These queues are empty in normal operation, so the
  # threshold is presence rather than a rate, and there is no volume at which a
  # dropped delete becomes acceptable.
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  # One period, because the condition is a gauge rather than a spike: a message
  # sitting in a dead letter queue is still there on the next evaluation, and
  # waiting for a second one only delays the page.
  evaluation_periods = 1

  # missing is not breaching. A queue with no traffic reports no data rather than
  # a zero, which is the normal state for all six of these, and treating that as
  # breaching would alarm continuously from the moment they are created.
  treat_missing_data = "notBreaching"

  alarm_actions = [module.alarms.sns_topic_arn]
  ok_actions    = [module.alarms.sns_topic_arn]

  metric_query {
    id          = "depth"
    expression  = join(" + ", [for i, _ in local.dlq_alarm_queues : "m${i}"])
    label       = "Dead letter queue depth"
    return_data = true
  }

  dynamic "metric_query" {
    for_each = { for i, name in local.dlq_alarm_queues : "m${i}" => name }

    content {
      id          = metric_query.key
      label       = metric_query.value
      return_data = false

      metric {
        namespace   = "AWS/SQS"
        metric_name = "ApproximateNumberOfMessagesVisible"
        dimensions  = { QueueName = metric_query.value }
        period      = 300
        stat        = "Maximum"
      }
    }
  }

  tags = { Name = "${local.prefix}-dlq-depth" }
}
