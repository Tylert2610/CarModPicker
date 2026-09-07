# The frontend distribution. Still hand-written: platform-modules/aws//modules/spa-frontend
# 1.3.1 cannot take the staging access gate without changing this resource. Its access_gate input
# is a single object variable that carries origin_verify_header_value, which is sensitive. A
# module input object with one sensitive member is marked sensitive as a whole when it crosses
# the module boundary, so inside the module every attribute derived from it, the path patterns,
# the target origin ids, the allowed methods, the cache policy ids, comes out sensitive too. The
# planned values are byte-identical to what is in state, but the sensitivity marks differ, and
# Terraform plans that as an in-place update. Laundering the mark with nonsensitive() would put
# the origin-verify secret into plan output, so the distribution stays here.
#
# The module is otherwise a match; adopt it once the gate's sensitive value reaches it through
# its own input rather than as a member of the access_gate object.

locals {
  frontend_origin_id           = "${local.prefix}-frontend-s3"
  staging_gate_login_origin_id = "${local.prefix}-access-gate-login"
  staging_gate_api_origin_id   = "${local.prefix}-api"

  # AWS managed CloudFront policies.
  cf_cache_policy_caching_optimized   = "658327ea-f89d-4fab-a63d-7e88639e58f6" # CachingOptimized
  cf_origin_request_policy_cors_s3    = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf" # CORS-S3Origin
  cf_response_headers_policy_security = "67f7725c-6f97-4210-82d7-5512b31e9d03" # SecurityHeadersPolicy
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = local.custom_domain ? ["www.${local.domain_name}", local.domain_name] : []
  price_class         = "PriceClass_100" # US + Europe only — cheapest tier

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = local.frontend_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Staging access gate: login Lambda function URL, reached through the /_auth/* behavior.
  dynamic "origin" {
    for_each = local.staging_gate_enabled ? [1] : []
    content {
      domain_name              = module.staging_access_gate[0].login_origin_domain_name
      origin_id                = local.staging_gate_login_origin_id
      origin_access_control_id = module.staging_access_gate[0].login_origin_access_control_id

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # Staging access gate: the HTTP API behind the site origin, so /api/* calls ride on the signed
  # cookies. The custom header is what the API's REQUEST authorizer checks.
  dynamic "origin" {
    for_each = local.staging_gate_enabled ? [1] : []
    content {
      domain_name = "api.${local.domain_name}"
      origin_id   = local.staging_gate_api_origin_id

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }

      custom_header {
        name  = module.staging_access_gate[0].origin_verify_header_name
        value = module.staging_access_gate[0].origin_verify_header_value
      }
    }
  }

  default_cache_behavior {
    target_origin_id       = local.frontend_origin_id
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id            = local.cf_cache_policy_caching_optimized
    origin_request_policy_id   = local.cf_origin_request_policy_cors_s3
    response_headers_policy_id = local.cf_response_headers_policy_security

    # Staging access gate: require the gate's signed cookies on every request.
    trusted_key_groups = local.staging_gate_enabled ? [module.staging_access_gate[0].key_group_id] : null

    # Rewrites /about → /about/index.html etc. so prerendered subdirectory
    # HTML files resolve cleanly from S3. Behind the staging access gate the
    # gate's function runs the same appHandler and then checks the session.
    function_association {
      event_type   = "viewer-request"
      function_arn = local.staging_gate_enabled ? module.staging_access_gate[0].viewer_request_function_arn : aws_cloudfront_function.frontend_uri_rewrite.arn
    }
  }

  # Staging access gate: /_auth/* to the login Lambda (login, callback, logout).
  dynamic "ordered_cache_behavior" {
    for_each = local.staging_gate_enabled ? [1] : []
    content {
      path_pattern             = module.staging_access_gate[0].auth_path_pattern
      target_origin_id         = local.staging_gate_login_origin_id
      viewer_protocol_policy   = "https-only"
      allowed_methods          = ["GET", "HEAD", "OPTIONS"]
      cached_methods           = ["GET", "HEAD"]
      cache_policy_id          = module.staging_access_gate[0].cache_policy_id_caching_disabled
      origin_request_policy_id = module.staging_access_gate[0].origin_request_policy_id_all_viewer_except_host_header

      function_association {
        event_type   = "viewer-request"
        function_arn = module.staging_access_gate[0].viewer_request_function_arn
      }
    }
  }

  # Staging access gate: /api/* to the HTTP API, signed cookies required.
  dynamic "ordered_cache_behavior" {
    for_each = local.staging_gate_enabled ? [1] : []
    content {
      path_pattern             = module.staging_access_gate[0].api_path_pattern
      target_origin_id         = local.staging_gate_api_origin_id
      viewer_protocol_policy   = "https-only"
      allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]
      cache_policy_id          = module.staging_access_gate[0].cache_policy_id_caching_disabled
      origin_request_policy_id = module.staging_access_gate[0].origin_request_policy_id_all_viewer_except_host_header
      trusted_key_groups       = [module.staging_access_gate[0].key_group_id]

      function_association {
        event_type   = "viewer-request"
        function_arn = module.staging_access_gate[0].viewer_request_function_arn
      }
    }
  }

  # Staging access gate: the SPA shell must stay fetchable WITHOUT the key group, because
  # CloudFront's own custom_error_response (403/404 to /index.html) carries no cookies. The gate
  # function still turns away browsers that ask for it directly without a session.
  dynamic "ordered_cache_behavior" {
    for_each = local.staging_gate_enabled ? [1] : []
    content {
      path_pattern           = "/index.html"
      target_origin_id       = local.frontend_origin_id
      viewer_protocol_policy = "redirect-to-https"
      allowed_methods        = ["GET", "HEAD"]
      cached_methods         = ["GET", "HEAD"]
      compress               = true

      cache_policy_id            = local.cf_cache_policy_caching_optimized
      origin_request_policy_id   = local.cf_origin_request_policy_cors_s3
      response_headers_policy_id = local.cf_response_headers_policy_security

      function_association {
        event_type   = "viewer-request"
        function_arn = module.staging_access_gate[0].viewer_request_function_arn
      }
    }
  }

  # React Router uses client-side routing — return index.html for all 403/404
  # responses from S3 so the SPA can handle the route itself.
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.custom_domain ? null : true
    acm_certificate_arn            = local.custom_domain ? aws_acm_certificate_validation.carmodpicker[0].certificate_arn : null
    ssl_support_method             = local.custom_domain ? "sni-only" : null
    minimum_protocol_version       = local.custom_domain ? "TLSv1.2_2021" : null
  }

  tags = { Name = "${local.prefix}-frontend" }
}
