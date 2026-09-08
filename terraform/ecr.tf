# ---------------------------------------------------------------------------
# Container registries for the per-domain FastAPI Lambdas, one repository per
# domain per environment. Section 3.1 of docs/migration/split-plan.md.
#
# The names come out as "carmodpicker-<env>/<domain>", so a slash namespaces
# every repository of one environment together in the console and a lifecycle
# rule that keeps the last ten tagged images means the last ten builds of that
# one domain rather than the last ten builds of the application.
#
# This is the whole of PR 9. The deploy role's push permissions are PR 10 and
# the functions that pull these images are PR 13 onward, so nothing consumes a
# repository yet. local.lambda_domains is defined here rather than in a later
# file because it is the single list those later PRs reuse: functions, IAM
# policies and routes all key off the same names, and a domain added in one
# place should not be a domain missing in another.
#
# The functions will be created by this same root, in this same account and
# region, so no repository policy is written. Same-account access needs only one
# side to grant it, and Lambda writes its own LambdaECRImageRetrievalPolicy
# statement onto the repository at CreateFunction. Setting
# repository_policy_principals would make Terraform own the whole document and
# drop that statement on the next apply, which is the failure that only shows up
# when Lambda later re-fetches the image.
# ---------------------------------------------------------------------------

locals {
  # The nine deployable domains from section 1 of the split plan, in the order
  # section 6.1 cuts them over. Later PRs add per-domain attributes (memory, the
  # tables each one owns, the secrets it reads) by widening this from a list to a
  # map; today nothing but ECR reads it, and a list is what that needs.
  lambda_domains = [
    "media",
    "build-logs",
    "moderation",
    "vehicles",
    "ingestion",
    "build-lists",
    "identity",
    "catalog",
    "users",
  ]
}

module "registry" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/ecr-repository"
  version = "~> 2.0"

  name_prefix = local.prefix

  # Every module-wide default is right here: IMMUTABLE tags, scan on push, keep
  # the last 10 images tagged "sha-", expire untagged after a day, AES256.
  # Immutability is what makes a sha- tag a reproducible deploy, and it is why
  # the build job in PR 12 needs a guard that skips a push when the tag already
  # exists rather than overwriting it.
  repositories = { for domain in local.lambda_domains : domain => {} }
}
