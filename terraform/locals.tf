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

  # What the frontend build should use as VITE_API_URL: always the API's own host, staging
  # included. Behind the gate the browser sends the request with credentials, the signed cookies
  # are scoped to Domain=staging.<domain> so a call from www.staging to api.staging carries them,
  # and the API's own authorizer checks them. The frontend appends /api itself.
  frontend_api_base_url = local.api_url

  # Row 8: gateway level enforcement of the identity access token, split into the two booleans the
  # two modules actually read. var.identity_jwt_mode is the one place the choice is written; these
  # exist so neither module block has to repeat the string comparison, and so the mode and the
  # environment's actual shape are reconciled in one place rather than two.
  #
  # The gate branch is additionally conditioned on local.staging_gate_enabled. "gate" names a
  # mechanism that only exists when the gate module is instantiated, so a workspace left on "gate"
  # while the gate is off would otherwise index a module with count 0 and fail the plan. Resolving
  # to false instead means an environment without a gate enforces nothing rather than failing,
  # which is the same relationship every other staging_gate_enabled consumer in this configuration
  # has.
  identity_jwt_gate_enforced   = var.identity_jwt_mode == "gate" && local.staging_gate_enabled
  identity_jwt_native_enforced = var.identity_jwt_mode == "native"

  dev_origins     = ["http://localhost", "http://localhost:3000", "http://localhost:4000"]
  allowed_origins = var.environment == "production" ? "" : join(",", concat(local.dev_origins, local.custom_domain ? ["https://${local.domain_name}", "https://www.${local.domain_name}"] : [local.frontend_url]))

  # The origin list API Gateway answers CORS preflight with, in apigateway.tf.
  #
  # This is deliberately NOT local.allowed_origins. That one is the Lambda's
  # ALLOWED_ORIGINS env var and it is the empty string on production, where
  # lambda.tf's `if value != ""` filter drops it from the environment so the
  # application falls back to the defaults baked into
  # backend/app/core/config.py. A gateway cors_configuration has no such
  # fallback: it is the literal list API Gateway matches Origin against, so
  # production has to be spelled out here rather than left empty.
  #
  # The three parts mirror what the application's CORSMiddleware actually
  # admits at runtime, so the gateway and the function agree rather than
  # disagree:
  #   - the site itself, apex and www, per environment
  #   - the localhost dev origins, which config.py's default carries in both
  #     environments and which cost nothing at the gateway
  #   - the published Chrome extension. config.py defaults CHROME_EXTENSION_IDS
  #     to the store id and nothing in Terraform sets it, so the extension's
  #     `chrome-extension://<id>` origin is part of the runtime list and would
  #     be silently dropped by a gateway list built from the site domains
  #     alone. The id is public: it is in every store URL and in the
  #     CWS_EXTENSION_ID GitHub variable.
  #
  # An unpacked development id overrides CHROME_EXTENSION_IDS on the function
  # only. Preflight for it is answered by the function today and would stop
  # being answered once route keys become explicit, which is a development-only
  # gap worth naming here rather than discovering later.
  chrome_extension_origins = ["chrome-extension://dbglgmnnfandmnacdpibkfggkadjikkg"]

  cors_allow_origins = concat(
    ["https://${local.domain_name}", "https://www.${local.domain_name}"],
    local.dev_origins,
    local.chrome_extension_origins,
  )
}
