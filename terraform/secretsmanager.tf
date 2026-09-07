module "app_secrets" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/app-secrets"
  version = "~> 1.6"

  name_prefix = local.prefix

  secrets = {
    "secret-key" = {
      description = "JWT signing key for the FastAPI backend"
      value       = var.secret_key
    }

    # Sentry DSN (Phase 2 / OBS-01).
    # Created empty by `terraform apply`; operator populates the value out-of-band
    # with `aws secretsmanager put-secret-value` after creating the Sentry project
    # manually per D-55 / terraform README "Bootstrap: Sentry".
    "sentry-dsn" = {
      description = "Sentry DSN for backend error reporting (Sentry project created manually per D-54). Populated via put-secret-value post-apply."
      value       = var.sentry_dsn
    }

    "app" = {
      description = "JSON map of runtime secrets read by the Lambda API at cold start"
      json = {
        SECRET_KEY = var.secret_key
        SENTRY_DSN = var.sentry_dsn
      }
    }
  }
}
