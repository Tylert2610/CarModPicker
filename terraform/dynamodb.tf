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
    })
  }
}

module "dynamodb" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/dynamodb-tables"
  version = "~> 1.6"

  name_prefix = local.prefix
  tables      = local.dynamodb_tables

  point_in_time_recovery = var.environment == "production"
  deletion_protection    = var.environment == "production"
  name_tag               = true
}
