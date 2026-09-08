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
# repository yet. local.lambda_domain_names is defined here rather than in a
# later file because it is the single list those later PRs reuse: functions, IAM
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
  # section 6.1 cuts them over. This is the ordered name list, and it is the one
  # thing that must stay in this order: the ECR repositories are keyed off it,
  # the deploy role's function ARNs are built from it, and section 3.6 makes the
  # alarm module's `lambda_function_names` positional, so a reorder rewrites
  # every metric math expression rather than being cosmetic.
  #
  # Per-domain attributes (memory, the tables each one owns, whether it reads a
  # secret) live in `local.lambda_domains` in lambda_domains.tf, which is a map
  # keyed by these names. It is deliberately not the same object: this list has
  # all nine from row 9 onward, because nine repositories exist and the deploy
  # role grants on all nine, while the map holds only the domains whose function
  # has actually been created. Rows 18 through 31 add one entry each.
  lambda_domain_names = [
    "media",
    "build-logs",
    "moderation",
    "vehicles",
    "admin",
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
  #
  # `force_delete` stays at the module default of false for every repository.
  # It is a destroy-time flag and the provider reads it from prior state, not
  # from configuration, so setting it here would not help the one repository
  # this change destroys. See the note on the ingestion rename below.
  repositories = { for domain in local.lambda_domain_names : domain => {} }
}

# ---------------------------------------------------------------------------
# The ingestion to admin rename, and the one manual step it needs.
#
# `ingestion` left local.lambda_domain_names and `admin` joined it, so this
# apply destroys carmodpicker-<env>/ingestion and creates carmodpicker-<env>/admin.
# In staging the old repository is not empty: row 11 pushed three images into it
# by hand and nothing has ever deployed from them.
#
# aws_ecr_repository refuses to delete a repository that still holds images
# unless force_delete is true, and force_delete is read from the resource's
# prior state at destroy time. A key removed from a for_each map has no
# configuration left to evaluate, so a value set in this file cannot reach the
# instance being destroyed. Flipping the module-wide switch in the same apply
# would change nothing and would also drop the guardrail on the eight
# repositories that Lambda really does pull from.
#
# So the three images are deleted first, out of band, and then this applies
# cleanly. They are disposable: three sha- tags beginning ef2e455d, d7a6eaf4
# and 30531f63, no function was ever created from them, and
# var.bootstrap_image_tag names a tag in every domain's own repository rather
# than in this one.
#
#   aws ecr list-images --region us-west-2 \
#     --repository-name carmodpicker-staging/ingestion \
#     --query 'imageIds[*]' > ids.json
#   aws ecr batch-delete-image --region us-west-2 \
#     --repository-name carmodpicker-staging/ingestion \
#     --image-ids file://ids.json
#
# Production has no repositories yet, so nothing is destroyed there and the
# first apply on main simply creates all nine under the new name.
#
# The alternative, two applies with force_delete true in between, costs an
# extra apply and leaves the flag on. Deleting three throwaway images is the
# smaller change.
# ---------------------------------------------------------------------------
