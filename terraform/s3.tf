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

module "lambda_artifacts" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-artifacts-bucket"
  version = "~> 1.6"

  bucket = "${local.prefix}-lambda-artifacts"

  lifecycle_rule_id                      = "expire-noncurrent-artifacts"
  noncurrent_version_expiration_days     = 30
  abort_incomplete_multipart_upload_days = 7
  # enable_sse and create_placeholder_object stay false: CarModPicker has neither today. Its
  # Lambda ships the placeholder as a local filename, not through S3.
}

# The frontend bucket, its public access block, the origin access control and the bucket policy
# live in module "frontend" (cloudfront.tf), alongside the distribution that reads them.
