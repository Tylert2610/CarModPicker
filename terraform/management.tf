# Account level housekeeping: the tag based resource group, Cost Explorer anomaly detection and
# the free budget alerts. All of it now comes from the shared app-baseline module.
module "app_baseline" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/app-baseline"
  version = "~> 1.6"

  name                = local.prefix
  notification_emails = ["tyler@webbpulse.com", "tylert2610@gmail.com"]

  resource_group_description = "All CarModPicker managed resources"
  resource_group_tag_filters = {
    Project = [local.project]
  }

  budgets = {
    "monthly-warn"     = { limit_amount = "30" }
    "monthly-critical" = { limit_amount = "60" }
  }
}
