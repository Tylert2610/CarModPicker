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

  # The nine per-domain function ARNs, written out rather than read off a module output, because
  # only some of the functions exist: PR 13 of docs/migration/split-plan.md creates `media` and
  # rows 18 through 31 add the other eight one at a time. Granting ahead of the resource is safe
  # for lambda:UpdateFunctionCode and InvokeFunction, which resolve at call time, and it is what
  # lets the deploy workflow in PR 12 land before the first function does. Reading the ARNs off
  # module.lambda_domain instead would shrink this policy to whatever exists today and mean an
  # IAM change riding along with every one of those eight rows. The name here has to stay in step
  # with the function_name lambda_domains.tf sets, "${local.prefix}-${domain}", which is the same
  # shape module.lambda_api used before row 32 retired it.
  lambda_domain_function_arns = [
    for domain in sort(local.lambda_domain_names) :
    "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.prefix}-${domain}"
  ]

  # The stream consumers from lambda_stream_consumers.tf, row 24 onward, written out by the same
  # method and for the same reason as the nine above. A consumer is deployed by the same
  # UpdateFunctionCode call a domain function is, because it runs a domain's image: row 24's runs
  # `catalog`'s, so the image-map job in deploy-backend.yml names this function against the
  # catalog image and the deploy would fail on AccessDenied without the grant here.
  #
  # This one reads the declared map rather than the gated one, which is the same "grant ahead of
  # the resource" choice the comment above makes: the gated map is empty while
  # `bootstrap_image_tag` is, and an IAM policy that empties itself during a bootstrap is how the
  # first deploy after the bootstrap fails.
  lambda_stream_consumer_function_arns = [
    for name in sort(keys(local.lambda_stream_consumers_declared)) :
    "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.prefix}-${name}"
  ]

  # Reading the shared "webbpulse" package out of CodeArtifact. Three statements because the three
  # actions take three different resources: GetAuthorizationToken is domain level, the read actions
  # are per repository, and sts:GetServiceBearerToken has no resource of its own at all.
  #
  # Held as its own list because two roles need exactly this and nothing more of it: the deploy
  # role, whose container build resolves the same package, and the pull request CI role at the
  # bottom of this file, for which these three statements are the entire permission set.
  codeartifact_read_policy_statements = [
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
      # sts:GetServiceBearerToken lives in the caller's identity policy rather than in any
      # CodeArtifact policy, which is why a resource policy alone is not enough. Without it
      # get-authorization-token fails with a denial that names no CodeArtifact action. The
      # condition pins it to CodeArtifact so the grant cannot mint a bearer token for another
      # service.
      sid       = "CodeArtifactBearerToken"
      actions   = ["sts:GetServiceBearerToken"]
      resources = ["*"]
      condition = {
        StringEquals = {
          "sts:AWSServiceName" = ["codeartifact.amazonaws.com"]
        }
      }
    },
  ]

  # Everything the container build needs: the CodeArtifact reads above, pull on the shared base
  # image, and push on this account's own nine domain repositories. Kept as its own list so the
  # deploy statements below stay readable, and so the shapes stay recognisably the ones the
  # artifacts root exports.
  shared_registry_policy_statements = concat(local.codeartifact_read_policy_statements, [
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
      # it is a separate statement on "*" rather than folded into the one above. It covers this
      # account's own registry as well as the shared one, so the push grant below needs no second
      # auth statement.
      sid       = "SharedBaseImageAuth"
      actions   = ["ecr:GetAuthorizationToken"]
      resources = ["*"]
    },
    {
      # Push a built domain image to this account's own registry, and read the manifest back.
      # BatchGetImage is what the build job's existing-tag guard calls: the repositories are
      # IMMUTABLE, so a rebuild of an already pushed sha- tag fails the push rather than
      # overwriting it, and the guard has to be able to see the tag before it tries.
      #
      # Get and SetRepositoryPolicy are here for the first apply of PR 13. Creating a container
      # image function makes Lambda write its own LambdaECRImageRetrievalPolicy statement onto
      # the repository, and that write happens under the caller's credentials.
      sid = "EcrPushDomainImages"
      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:SetRepositoryPolicy",
      ]
      resources = module.registry.repository_arns_list
    },
  ])
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
      # The `s3:PutObject`/`s3:GetObject` statement on the artifacts bucket was the first entry
      # here until row 32. It let `backend-deploy.yml` upload the monolith's zip; the bucket, the
      # workflow and the function are all gone, so the grant goes with them. Section 6.5 names
      # dropping it as part of the retirement, and it is the one privilege this row actually takes
      # away from the deploy role rather than merely narrowing.
      #
      # Statement order is otherwise preserved. The module renders a one-element list as a bare
      # JSON string and the order below is the order the hand-written policy had, so the remaining
      # statements keep their rendered shape and only the removed one moves anything.
      #
      # One statement over thirteen function ARNs, because the nine domain functions and the four
      # stream consumers all take the same UpdateFunctionCode call with an ECR image tag the build
      # job has already pushed. It was fourteen until row 32: the monolith was in this list too,
      # and it was the one entry whose payload was an S3 zip rather than an image.
      {
        actions = [
          "lambda:UpdateFunctionCode",
          "lambda:PublishVersion",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:GetFunctionCodeSigningConfig",
        ]
        resources = concat(
          local.lambda_domain_function_arns,
          local.lambda_stream_consumer_function_arns,
        )
      },
      # Invoke a domain function directly for the post deploy smoke probe. Between PR 13 and that
      # domain's cutover PR the function has no API Gateway route at all, so a synthetic HTTP API
      # event through Invoke is the only way to prove a freshly shipped image answers. The
      # monolith was left out on purpose while it existed, because it was reachable at its public
      # /health URL and needed no invoke grant to be probed. Row 32 retired it and this statement
      # is unchanged by that: it never named the monolith.
      {
        actions   = ["lambda:InvokeFunction"]
        resources = local.lambda_domain_function_arns
      },
      # Read the HTTP API access log, for scripts/verify_route_cut.sh. Section 6.3 of
      # docs/migration/split-plan.md makes the access log's `routeKey` field the check that a
      # strangler cut actually took effect: before a cut every entry for the prefix reads
      # "$default", after it they read the explicit route key, and nothing visible over HTTP
      # distinguishes the two. So the verification has to read this log group, and it is the only
      # log group it reads. Scoped to that one group rather than to the account's logs, and to the
      # one read action, because a deploy role that can read every log group is a wider credential
      # than a route check needs.
      {
        actions   = ["logs:FilterLogEvents"]
        resources = ["arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/apigateway/${local.prefix}-api:*"]
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
    # Registries: read the webbpulse CodeArtifact domain so CI can pip install the shared
    # "webbpulse" package and npm install @webbpulse/*, pull the shared Lambda base image, and
    # push the built domain images to this account's own repositories.
    local.shared_registry_policy_statements,
  )
}

# ---------------------------------------------------------------------------
# The role pull request CI assumes, separate from the deploy role above.
#
# backend-ci.yml needs an AWS identity for one thing only: minting a read only
# CodeArtifact token so pip can install the "webbpulse" package, which is
# published to CodeArtifact and never to PyPI. It was doing that with the deploy
# role, which holds lambda:UpdateFunctionCode and ecr:PutImage and whose trust
# admits every subject in the repository including a pull request branch. That
# means any branch that can open a pull request could assume a role that
# deploys.
#
# This role carries the CodeArtifact statements and nothing else, and its trust
# names the pull request subject plus the two long lived branch refs rather than
# a wildcard, so a push triggered job on staging or main can use it too.
# ---------------------------------------------------------------------------
module "github_actions_ci_role" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/github-actions-role"
  version = "~> 1.1"

  role_name        = "${local.prefix}-github-actions-ci"
  role_description = "Read only CodeArtifact access for pull request CI in WebbPulse/CarModPicker. Deploy permissions live on the separate github-actions-deploy role."

  # The deploy role's module call owns this account's single
  # token.actions.githubusercontent.com provider; an account holds at most one
  # per URL, so this call trusts that one rather than creating a second.
  create_oidc_provider = false
  oidc_provider_arn    = module.github_actions_role.oidc_provider_arn

  # CarModPicker predates GitHub's immutable subject claims, so its
  # sub_claim_prefix is still the plain "repo:WebbPulse/CarModPicker" the deploy
  # role above uses. Newer WebbPulse repositories get
  # "repo:WebbPulse@185014056/<repo>@<id>" instead, and a trust policy written in
  # the wrong shape is denied at AssumeRoleWithWebIdentity, so read
  # /repos/WebbPulse/<repo>/actions/oidc/customization/sub before reusing this.
  subjects = [
    "repo:WebbPulse/CarModPicker:pull_request",
    "repo:WebbPulse/CarModPicker:ref:refs/heads/staging",
    "repo:WebbPulse/CarModPicker:ref:refs/heads/main",
  ]

  inline_policy_name = "codeartifact-read"

  policy_statements = local.codeartifact_read_policy_statements
}
