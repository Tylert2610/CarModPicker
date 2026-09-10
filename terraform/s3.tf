# ---------------------------------------------------------------------------
# User image uploads — private, accessed via presigned URLs
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "user_images" {
  bucket = "${local.prefix}-user-images"
}

resource "aws_s3_bucket_public_access_block" "user_images" {
  bucket = aws_s3_bucket.user_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Page HTML snapshots from the chrome-extension scrape flow
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "crawl_data" {
  bucket = "${local.prefix}-crawl-data"
}

resource "aws_s3_bucket_public_access_block" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Transition HTML snapshots to Glacier Deep Archive after 90 days. Restricted
# to crawl-data ONLY; user-images stays hot (latency-sensitive serve path).
resource "aws_s3_bucket_lifecycle_configuration" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

  rule {
    id     = "archive-old-snapshots"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

# ---------------------------------------------------------------------------
# The Lambda artifacts bucket is gone, retired with the monolith in row 32
# ---------------------------------------------------------------------------
#
# `module "lambda_artifacts"` built `<prefix>-lambda-artifacts` from
# `platform-modules/aws//modules/lambda-artifacts-bucket`, a versioned bucket with a 30-day
# noncurrent expiry that `backend-deploy.yml` uploaded the monolith's zip to, keyed by commit sha.
# Nothing writes a zip any more: the nine domain functions and the four stream consumers all
# deploy as OCI images from the `ecr.tf` repositories, so the bucket had no writer left once row
# 31 cut the ninth domain. Section 6.5.
#
# This is the one destroy in this row that removes stored data rather than a control-plane object,
# and it is worth being explicit about what goes with it. The bucket is versioned, so its contents
# are every monolith zip from the last 30 days plus the current version of each key. The module
# sets `force_destroy` and the bucket empties on destroy rather than failing the apply on a
# non-empty bucket. Those zips are the only artifact of the retired deploy path, they are
# reproducible from their commit shas, and no rollback in this repository reads one: reverting
# this PR re-creates the bucket empty and no workflow refills it. The rollback paragraph in the
# PR body says what that means in practice.

#
# Correction after the row 32 apply: the module defaults `force_destroy` to false and this
# configuration never set it, so the apply destroyed the versioning, lifecycle and public access
# block resources and then failed on the bucket itself with BucketNotEmpty. The bucket still holds
# every monolith zip version. The block below re-adopts it as a bare resource with
# `force_destroy = true` so the provider can empty it (all versions and delete markers) on the
# next destroy. It is temporary: the follow-up PR removes this resource and the `moved` block
# together, and that apply is the one that deletes the bucket. Nothing else references it.
moved {
  from = module.lambda_artifacts.aws_s3_bucket.this
  to   = aws_s3_bucket.legacy_lambda_artifacts
}

resource "aws_s3_bucket" "legacy_lambda_artifacts" {
  bucket        = "${local.prefix}-lambda-artifacts"
  force_destroy = true

  tags = {
    Name = "${local.prefix}-lambda-artifacts"
  }
}

# The frontend bucket, its public access block, the origin access control and the bucket policy
# live in module "frontend" (cloudfront.tf), alongside the distribution that reads them.
