locals {
  project = "carmodpicker"

  # Use as a prefix for all resource names: "${local.prefix}-vpc", etc.
  prefix = "${local.project}-${var.environment}"

  # Applied to every resource via provider default_tags.
  # Add resource-specific tags inline where needed.
  common_tags = {
    Project     = local.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  custom_domain = coalesce(var.custom_domain_enabled, var.environment == "production" || var.staging_profile == "full")

  domain_name       = var.environment == "production" ? var.domain_name : "staging.${var.domain_name}"
  active_domain     = local.custom_domain ? local.domain_name : var.domain_name
  parent_delegation = var.environment == "staging" && local.custom_domain

  email_from = coalesce(var.email_from, "no-reply@${local.active_domain}")

  # Staging access gate: only a staging workspace with the full profile (custom domain) and the
  # WebbPulse-Platform flag gets it. Production evaluates both to false and plans a no-op.
  staging_gate_enabled = var.environment == "staging" && var.staging_access_gate && local.custom_domain
  staging_gate_count   = local.staging_gate_enabled ? 1 : 0

  frontend_url = module.frontend.frontend_url
  api_url      = module.api.api_url

  # What the frontend build should use as VITE_API_URL. Behind the gate the browser must call the
  # API through the site origin (https://www.staging.<domain>/api/*) so the signed cookies travel
  # with the request; the frontend appends /api itself.
  frontend_api_base_url = local.staging_gate_enabled ? local.frontend_url : local.api_url

  dev_origins     = ["http://localhost", "http://localhost:3000", "http://localhost:4000"]
  allowed_origins = var.environment == "production" ? "" : join(",", concat(local.dev_origins, local.custom_domain ? ["https://${local.domain_name}", "https://www.${local.domain_name}"] : [local.frontend_url]))
}
