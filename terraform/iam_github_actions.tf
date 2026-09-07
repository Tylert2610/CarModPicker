# ---------------------------------------------------------------------------
# Shared registry (WebbPulse-Artifacts account)
# ---------------------------------------------------------------------------

locals {
  # Account id of the WebbPulse-Artifacts account, which owns the "webbpulse" CodeArtifact domain
  # and the shared ECR base images. Hardcoded on purpose: a remote state data source would couple
  # every plan in this root to the artifacts workspace's state, for a value that is an AWS account
  # id and therefore never changes. If the registry ever moves accounts, this one line moves with
  # it.
  artifacts_account_id = "432410731887"

  codeartifact_domain = "webbpulse"

  # Rendered from the artifacts root's codeartifact_consumer_policy_statements output. The domain
  # and repository policies over there allow this account in; these statements are the identity
  # half, and both halves have to agree before a build can read a package.
  codeartifact_domain_arn = "arn:aws:codeartifact:${var.aws_region}:${local.artifacts_account_id}:domain/${local.codeartifact_domain}"

  codeartifact_repository_arns = [
    for repository in ["npm", "npm-store", "pypi-store", "python", "shared"] :
    "arn:aws:codeartifact:${var.aws_region}:${local.artifacts_account_id}:repository/${local.codeartifact_domain}/${repository}"
  ]

  # The shared base layer the per-domain FastAPI Lambdas are built on. The region is written out
  # rather than taken from var.aws_region: the repository lives in us-west-2 in the artifacts
  # account wherever this root happens to deploy, and Lambda cannot pull an image across regions,
  # so a consumer function has to be in us-west-2 too.
  shared_base_image_repository_arn = "arn:aws:ecr:us-west-2:${local.artifacts_account_id}:repository/webbpulse/python-lambda-base"

  # CodeArtifact read plus the sts:GetServiceBearerToken that get-authorization-token needs, and
  # pull on the shared base image. Kept as its own list so the deploy statements above stay
  # readable, and so the shapes stay recognisably the ones the artifacts root exports.
  shared_registry_policy_statements = [
    {
      sid       = "CodeArtifactToken"
      actions   = ["codeartifact:GetAuthorizationToken"]
      resources = [local.codeartifact_domain_arn]
    },
    {
      sid = "CodeArtifactRead"
      actions = [
        "codeartifact:DescribePackageVersion",
        "codeartifact:DescribeRepository",
        "codeartifact:GetPackageVersionAsset",
        "codeartifact:GetPackageVersionReadme",
        "codeartifact:GetRepositoryEndpoint",
        "codeartifact:ListPackageVersionAssets",
        "codeartifact:ListPackageVersionDependencies",
        "codeartifact:ListPackageVersions",
        "codeartifact:ListPackages",
        "codeartifact:ReadFromRepository",
      ]
      resources = local.codeartifact_repository_arns
    },
    {
      # sts:GetServiceBearerToken has no resource of its own, and it lives in the caller's identity
      # policy rather than in any CodeArtifact policy, which is why a resource policy alone is not
      # enough. The condition pins it to CodeArtifact so the grant cannot mint a bearer token for
      # another service.
      sid       = "CodeArtifactBearerToken"
      actions   = ["sts:GetServiceBearerToken"]
      resources = ["*"]
      condition = {
        StringEquals = {
          "sts:AWSServiceName" = ["codeartifact.amazonaws.com"]
        }
      }
    },
    {
      sid = "SharedBaseImagePull"
      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
      ]
      resources = [local.shared_base_image_repository_arn]
    },
    {
      # GetAuthorizationToken is a registry level action with no resource of its own, which is why
      # it is a separate statement on "*" rather than folded into the one above.
      sid       = "SharedBaseImageAuth"
      actions   = ["ecr:GetAuthorizationToken"]
      resources = ["*"]
    },
  ]
}

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
        resources = ["${module.lambda_artifacts.bucket_arn}/*"]
      },
      {
        actions = [
          "lambda:UpdateFunctionCode",
          "lambda:PublishVersion",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:GetFunctionCodeSigningConfig",
        ]
        resources = [module.lambda_api.function_arn]
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
    # Shared registry: read the webbpulse CodeArtifact domain so CI can pip install the shared
    # "webbpulse" package and npm install @webbpulse/*, and pull the shared Lambda base image.
    local.shared_registry_policy_statements,
  )
}
