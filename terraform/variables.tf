variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "environment must be 'production' or 'staging'"
  }
}

variable "custom_domain_enabled" {
  description = "Provision Route53, ACM and custom hostnames. null = production or staging_profile 'full'."
  type        = bool
  default     = null
  nullable    = true
}

variable "domain_name" {
  description = "Registered apex domain. Production serves it directly; staging serves staging.<domain_name> from a delegated child zone."
  type        = string
  default     = "carmodpicker.com"
}

variable "parent_route53_zone_id" {
  description = "Hosted zone id of <domain_name> in the production account. Staging writes the NS delegation for its child zone into it. Pushed to the staging workspace by WebbPulse-Platform."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.environment != "staging" || !coalesce(var.custom_domain_enabled, var.staging_profile == "full") || var.parent_route53_zone_id != null
    error_message = "parent_route53_zone_id must be set when environment is 'staging' and the custom domain is on: the staging.<domain_name> zone is delegated from the parent zone owned by the production workspace. WebbPulse-Platform pushes it to the workspace."
  }
}

variable "route53_write_role_arn" {
  description = "IAM role in the production account assumed to write the NS delegation record into parent_route53_zone_id. Pushed to the staging workspace by WebbPulse-Platform; null means no cross-account provider is configured."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.environment != "staging" || !coalesce(var.custom_domain_enabled, var.staging_profile == "full") || var.route53_write_role_arn != null
    error_message = "route53_write_role_arn must be set when environment is 'staging' and the custom domain is on: the NS delegation for staging.<domain_name> is written into the parent zone through that role. WebbPulse-Platform pushes it to the workspace."
  }
}

variable "api_throttle_burst_limit" {
  description = "HTTP API $default stage throttling burst limit"
  type        = number
  default     = 50
}

variable "api_throttle_rate_limit" {
  description = "HTTP API $default stage steady-state requests per second"
  type        = number
  default     = 25
}

# Application secrets (stored in Secrets Manager, values injected via HCP workspace vars)
variable "secret_key" {
  description = "JWT signing secret for the FastAPI backend"
  type        = string
  sensitive   = true
}

variable "email_from" {
  description = "Sender address for transactional email. null = no-reply@ the domain SES is verified for (the served domain with a custom domain, the apex otherwise)."
  type        = string
  default     = null
  nullable    = true
}

# ---------------------------------------------------------------------------
# Observability (Phase 2 - OBS-01 Sentry, OBS-02 EMF/alarms)
# ---------------------------------------------------------------------------

variable "sentry_dsn" {
  description = "Sentry DSN for backend error reporting. Empty = Sentry disabled (env-gate handles gracefully). Populated out-of-band via `aws secretsmanager put-secret-value` per D-55."
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_release" {
  description = "Sentry release identifier (typically git commit SHA, set by GitHub Actions per D-02)."
  type        = string
  default     = ""
}

variable "staging_profile" {
  description = "How much of the stack this environment provisions. 'none' means the environment is switched off and must not be built. Set on the workspace by the WebbPulse-Organization workspace factory."
  type        = string
  default     = "full"

  validation {
    condition     = contains(["none", "reduced", "full"], var.staging_profile)
    error_message = "staging_profile must be one of 'none', 'reduced', or 'full'."
  }

  validation {
    condition     = var.staging_profile != "none"
    error_message = "Refusing to plan: staging_profile is 'none', so this environment is switched off and no resources should be created in it. To stand this environment up, change staging_profile to 'reduced' or 'full' on the workspace in WebbPulse-Organization/bootstrap/locals.tf."
  }
}

# ---------------------------------------------------------------------------
# Staging access gate (platform-modules/aws//modules/staging-access-gate)
# ---------------------------------------------------------------------------

variable "staging_access_gate" {
  description = "Put the staging site and API behind the shared staging access gate (Cognito sign-in plus CloudFront signed cookies). WebbPulse-Platform sets this on staging workspaces only; production never receives it and every gate resource is skipped there."
  type        = bool
  default     = false
}

variable "staging_access_users" {
  description = "Email addresses allowed through the staging access gate; each becomes an invited Cognito user. WebbPulse-Platform sets this on staging workspaces only; production never receives it."
  type        = list(string)
  default     = []

  validation {
    condition     = !var.staging_access_gate || length(var.staging_access_users) > 0
    error_message = "staging_access_users must list at least one email when staging_access_gate is true. An empty list is a gate nobody can open."
  }
}
