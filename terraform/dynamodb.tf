locals {
  dynamodb_tables = jsondecode(file("${path.module}/dynamodb_tables.json"))
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

moved {
  from = aws_dynamodb_table.tables
  to   = module.dynamodb.aws_dynamodb_table.this
}
