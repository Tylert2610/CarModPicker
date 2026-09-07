# The SPA: private S3 origin, CloudFront distribution, origin access control, bucket policy and
# the apex/www alias records, all from the shared platform module. The certificate (acm.tf), the
# hosted zone (route53.tf, via module.staging_dns) and the CloudFront Function
# (cloudfront_function.tf) stay here because they need providers or code the module does not own.
module "frontend" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/spa-frontend"
  version = "~> 1.3"

  name                       = "${local.prefix}-frontend"
  origin_access_control_name = "${local.prefix}-frontend-oac"
  origin_id                  = "${local.prefix}-frontend-s3"
  bucket_policy_sid          = "AllowCloudFrontOAC"

  aliases             = local.custom_domain ? ["www.${local.domain_name}", local.domain_name] : []
  acm_certificate_arn = one(aws_acm_certificate_validation.carmodpicker[*].certificate_arn)

  # Rewrites /about to /about/index.html etc. so prerendered subdirectory HTML resolves cleanly
  # from S3. Ignored while the access gate is attached: the gate function runs the same handler.
  viewer_request_function_arn = aws_cloudfront_function.frontend_uri_rewrite.arn

  # cache_mode "policies" and the CachingOptimized cache policy are the module defaults.
  origin_request_policy_id   = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf" # CORS-S3Origin
  response_headers_policy_id = "67f7725c-6f97-4210-82d7-5512b31e9d03" # SecurityHeadersPolicy

  distribution_tags = { Name = "${local.prefix}-frontend" }

  # Staging access gate: the login function URL origin, the API origin with the origin-verify
  # header, the ordered behaviors and the trusted key groups. Null in production, a no-op there.
  access_gate = local.staging_gate_enabled ? {
    key_group_id                                           = module.staging_access_gate[0].key_group_id
    viewer_request_function_arn                            = module.staging_access_gate[0].viewer_request_function_arn
    login_origin_domain_name                               = module.staging_access_gate[0].login_origin_domain_name
    login_origin_access_control_id                         = module.staging_access_gate[0].login_origin_access_control_id
    login_origin_id                                        = "${local.prefix}-access-gate-login"
    auth_path_pattern                                      = module.staging_access_gate[0].auth_path_pattern
    api_origin_domain_name                                 = "api.${local.domain_name}"
    api_origin_id                                          = "${local.prefix}-api"
    api_path_pattern                                       = module.staging_access_gate[0].api_path_pattern
    origin_verify_header_name                              = module.staging_access_gate[0].origin_verify_header_name
    origin_verify_header_value                             = module.staging_access_gate[0].origin_verify_header_value
    cache_policy_id_caching_disabled                       = module.staging_access_gate[0].cache_policy_id_caching_disabled
    origin_request_policy_id_all_viewer_except_host_header = module.staging_access_gate[0].origin_request_policy_id_all_viewer_except_host_header
  } : null

  create_dns_records = local.custom_domain
  zone_id            = module.staging_dns.zone_id
  dns_records = {
    www  = "www.${local.domain_name}"
    apex = local.domain_name
  }
}
