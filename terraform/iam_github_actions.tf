# GitHub Actions OIDC provider and deploy role, from the shared github-actions-role module. The
# provider is separate from the HCP Terraform one (app.terraform.io) that this workspace's own
# dynamic credentials use; this one lets GitHub Actions workflows assume an AWS role through
# short-lived OIDC tokens with no long-lived keys in GitHub.
#
# The statement order below is the order the hand-written policy had, and each statement lists
# its actions and resources exactly as before, because the module renders a one-element list as
# a bare JSON string. That keeps the stored policy document byte-identical.
module "github_actions_role" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/github-actions-role"
  version = "~> 1.1"

  role_name = "${local.prefix}-github-actions-deploy"
  subjects  = ["repo:WebbPulse/CarModPicker:*"]

  policy_statements = concat(
    [
      # Lambda: upload the zip to the artifacts bucket, then point the function at it
      {
        actions   = ["s3:PutObject", "s3:GetObject"]
        resources = ["${aws_s3_bucket.lambda_artifacts.arn}/*"]
      },
      {
        actions = [
          "lambda:UpdateFunctionCode",
          "lambda:PublishVersion",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:GetFunctionCodeSigningConfig",
        ]
        resources = [aws_lambda_function.api.arn]
      },
      # S3: sync frontend build artefacts
      {
        actions = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        resources = [
          module.frontend.bucket_arn,
          "${module.frontend.bucket_arn}/*",
        ]
      },
      # CloudFront: invalidate the cache after a frontend deploy
      {
        actions = [
          "cloudfront:CreateInvalidation",
          "cloudfront:GetInvalidation",
        ]
        resources = [module.frontend.distribution_arn]
      },
    ],
    # Staging access gate: let the deploy role read the origin-verify header value, so a pipeline
    # step that must call api.staging.<domain> directly (smoke test, health check) can get past
    # the API authorizer. Production adds nothing here.
    local.staging_gate_enabled ? [
      {
        actions   = ["ssm:GetParameter"]
        resources = [module.staging_access_gate[0].origin_verify_ssm_parameter_arn]
      },
    ] : [],
  )
}
