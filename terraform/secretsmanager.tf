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
        # Three keys, and after row 13 of docs/identity-adoption.md they are read
        # by three different functions rather than by all of them.
        #
        # SECRET_KEY is down to one caller pair: the admin price alerts consumer
        # signs the unsubscribe link and admin's unsubscribe route verifies it.
        # It is no longer the session signing key; see variables.tf.
        #
        # SENTRY_DSN is read by the monolith only. The nine domain functions
        # report through OpenTelemetry and none of them calls init_sentry, which
        # is why none of them needs this secret on that account.
        #
        # EXTENSION_API_KEY is catalog's, for the X-API-Key header on
        # POST /api/parts/price-history. It is independent of the session layer
        # row 13 retired, because its callers are machines with no user account.
        SECRET_KEY        = var.secret_key
        SENTRY_DSN        = var.sentry_dsn
        EXTENSION_API_KEY = var.extension_api_key

        # Row 9 of the identity adoption plan. The two OAuth client secrets,
        # read at cold start by `build_oauth_client_secrets` in
        # `backend/app/composition/identity.py` and passed to the package as an
        # argument rather than set as a settings field, so they never reach a
        # repr, a validation error or a settings log line.
        #
        # Here rather than as Lambda environment variables on the identity
        # function, which is this estate's rule for every secret: a client
        # secret in a function's environment is visible in the console, in
        # get-function-configuration, and in every plan that touches the
        # function. The two client IDs are not secret and do travel as
        # environment variables, in terraform/lambda_domains.tf.
        #
        # SCREAMING_SNAKE to match the three keys above. The package's provider
        # names are lowercase and the mapping from one to the other is
        # OAUTH_SECRET_KEYS in the composition root.
        #
        # An empty value is a working state and not a hole: the composition root
        # treats an empty string as an absent key, so a provider with no secret
        # is simply not advertised and its start route answers 503.
        OAUTH_GOOGLE_CLIENT_SECRET = var.oauth_google_client_secret
        OAUTH_GITHUB_CLIENT_SECRET = var.oauth_github_client_secret
      }
    }
  }
}
