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

moved {
  from = aws_secretsmanager_secret.secret_key
  to   = module.app_secrets.aws_secretsmanager_secret.this["secret-key"]
}

moved {
  from = aws_secretsmanager_secret_version.secret_key
  to   = module.app_secrets.aws_secretsmanager_secret_version.this["secret-key"]
}

moved {
  from = aws_secretsmanager_secret.sentry_dsn
  to   = module.app_secrets.aws_secretsmanager_secret.this["sentry-dsn"]
}

# Inert in staging, where var.sentry_dsn is empty so neither the old count instance nor the
# module version exists. In production it carries the real version across.
moved {
  from = aws_secretsmanager_secret_version.sentry_dsn[0]
  to   = module.app_secrets.aws_secretsmanager_secret_version.this["sentry-dsn"]
}

moved {
  from = aws_secretsmanager_secret.app
  to   = module.app_secrets.aws_secretsmanager_secret.this["app"]
}

moved {
  from = aws_secretsmanager_secret_version.app
  to   = module.app_secrets.aws_secretsmanager_secret_version.this["app"]
}
