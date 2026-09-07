# GitHub Actions deploy role, from the shared platform module. The role trusts GitHub's OIDC
# provider (separate from the HCP Terraform OIDC provider at app.terraform.io) so workflows get
# short-lived credentials instead of long-lived AWS keys. The role ARN is unchanged by the move,
# so AWS_DEPLOY_ROLE_ARN on the GitHub environments stays as it is.
module "github_actions_role" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/github-actions-role"
  version = "~> 1.3"

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
        actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
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
