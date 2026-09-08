module "app_secrets" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/app-secrets"
  version = "~> 1.6"

  name_prefix = local.prefix

  # One secret per environment. The Lambda API reads this JSON blob at cold start
  # through APP_SECRETS_ARN and nothing reads the values individually, so the
  # standalone secret-key and sentry-dsn secrets that predated it are gone.
  secrets = {
    "app" = {
      description = "JSON map of runtime secrets read by the Lambda API at cold start"
      json = {
        SECRET_KEY        = var.secret_key
        SENTRY_DSN        = var.sentry_dsn
        EXTENSION_API_KEY = var.extension_api_key
      }
    }
  }
}
