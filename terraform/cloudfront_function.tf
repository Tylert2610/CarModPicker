# CloudFront Function: apex→www 301 redirect + URI rewrite for prerendered
# SPA routes.
#
# Host rules:
#   carmodpicker.com      → 301 → https://www.carmodpicker.com<uri><query>
#   www.carmodpicker.com  → fall through to URI rewrite below
#
# URI rewrite rules (for www host):
#   /              → untouched (CloudFront default_root_object handles this)
#   /foo/          → /foo/index.html
#   /foo           → /foo/index.html          (extensionless, treated as directory)
#   /foo.js        → untouched                (real asset)
#
# Paths that point at SPA routes we did NOT prerender (e.g. /parts/123) will
# rewrite to /parts/123/index.html, S3 will 404, and CloudFront's
# custom_error_response falls back to /index.html — same SPA-shell behavior
# as before, no regression.
#
# The logic itself lives in cloudfront_functions/app_handler.js.tftpl as
# appHandler(event) so the staging access gate can run the same code inside
# its own function; this resource wraps it as handler(event). On staging with
# the gate on, the distribution associates the gate's function instead and
# this one simply sits unused.

resource "aws_cloudfront_function" "frontend_uri_rewrite" {
  name    = "${local.prefix}-frontend-uri-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Redirect apex→www and rewrite extensionless paths to index.html."
  publish = true
  code = templatefile("${path.module}/cloudfront_functions/uri_rewrite.js.tftpl", {
    app_handler = templatefile("${path.module}/cloudfront_functions/app_handler.js.tftpl", { domain = local.active_domain })
  })
}
