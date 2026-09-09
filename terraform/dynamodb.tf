locals {
  # Generated from the application's own table specs by
  # backend/scripts/export_dynamo_tables.py, so Terraform cannot drift from the code.
  # tests/db/test_dynamo_tables_json_up_to_date.py fails until a regenerated file is
  # committed.
  dynamodb_table_specs = jsondecode(file("${path.module}/dynamodb_tables.json"))

  # Point in time recovery is on for every table in production except the rate limiter's.
  # Its items are request counters that expire within their own window, so there is
  # nothing there worth restoring to a point in time, and paying continuous backup on a
  # hot, high churn, entirely disposable table is waste rather than safety. Portfolio's
  # declaration of the same table sets point_in_time_recovery = false for the same reason.
  #
  # The override lives here rather than in the generated JSON because that file is
  # rewritten from the application specs, which describe table shape and know nothing
  # about per environment durability.
  dynamodb_tables = {
    for name, spec in local.dynamodb_table_specs :
    name => merge(spec, {
      # null defers to the module-wide point_in_time_recovery input. The key is merged
      # onto every table rather than only onto rate-limits because a conditional whose
      # branches produce different object shapes will not convert to a map.
      point_in_time_recovery = name == "rate-limits" ? false : null

      # null on the twenty one tables that are not streamed, which is what a table
      # without a stream has in state, so they plan no change.
      stream_view_type = lookup(local.dynamodb_stream_view_types, name, null)
    })
  }

  # Streams, split plan row 22 and section 7. Four tables, each because a later seam
  # reads its stream, and NEW_AND_OLD_IMAGES on all four because every one of those
  # seams needs the old image:
  #
  #   users          seam 1, the delete cascade. Five domains delete their own rows
  #                  when a user is tombstoned, and a handler that has to know which
  #                  rows to delete needs the item as it was.
  #   parts          seam 2, the part purge. Same shape, smaller blast radius.
  #   votes          seam 3, the net_votes denormalisation. catalog recomputes the
  #                  count from the vote that changed, so it needs the old value as
  #                  well as the new to know which way the total moved.
  #   part_listings  seam 4, the price alert email. admin compares the new price
  #                  against the old to decide whether the price actually dropped.
  #
  # The view type is chosen once and cannot be revised. DynamoDB does not allow
  # editing a StreamViewType after the stream exists: changing it disables and
  # re-creates the stream, which mints a new stream ARN and detaches every event
  # source mapping reading the old one. Picking the widest view type here is
  # deliberate, because narrowing later is free and widening later is not.
  # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html
  #
  # Enabling a stream on a table that already exists is an in-place UpdateTable and
  # never replaces the table, which is what makes this safe to apply to live staging
  # and production tables.
  #
  # Nothing consumes these streams yet. The consumers are Lambda event source
  # mappings that arrive with the seams in rows 24 and 25, so this row turns the
  # streams on and creates the dead letter queues those mappings will fail into,
  # and creates no mapping and no consumer function of its own.
  dynamodb_stream_view_types = {
    users         = "NEW_AND_OLD_IMAGES"
    parts         = "NEW_AND_OLD_IMAGES"
    votes         = "NEW_AND_OLD_IMAGES"
    part_listings = "NEW_AND_OLD_IMAGES"
  }
}

module "dynamodb" {
  source = "app.terraform.io/WebbPulse/platform-modules/aws//modules/dynamodb-tables"

  # 2.5, for the per-table stream_view_type the four streams below need. The
  # module-wide stream_enabled and stream_view_type pair this module had before
  # is one value for every table the call creates, and this call creates all
  # twenty five, so the pair cannot stream four of them and leave the rest alone.
  #
  # The pin moves from 1.6 to 2.5 rather than to a 1.x: the registry's 1.x line
  # ends at 1.8.0 and the module is on 2.x, so the release carrying the new field
  # is 2.5.0. Nothing in the 2.x line changed this module's inputs, which is why
  # the jump is a pin change and not a migration.
  version = "~> 2.5"

  name_prefix = local.prefix
  tables      = local.dynamodb_tables

  point_in_time_recovery = var.environment == "production"
  deletion_protection    = var.environment == "production"
  name_tag               = true
}
