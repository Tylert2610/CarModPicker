# The frontend: private S3 bucket, origin access control, bucket policy, CloudFront distribution
# and the apex and www alias records, all from the shared spa-frontend module. The certificate
# (acm.tf), the hosted zone (route53.tf) and the CloudFront Function (cloudfront_function.tf)
# stay outside the module: a module has one aws provider, and the certificate needs us-east-1.
#
# The staging access gate is attached with the access_gate object in its direct subdomain shape:
# the login origin, /_auth/*, the unsigned /index.html behavior and the key group on the default
# behavior. No API members, because the frontend calls api.staging.<domain> directly and the
# gate's own API authorizer checks the same signed cookies there. Nothing on this distribution
# reads the origin verification header value, so access_gate_origin_verify_header_value is unset.
module "frontend" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/spa-frontend"
  version = "~> 1.1"

  name                       = "${local.prefix}-frontend"
  origin_access_control_name = "${local.prefix}-frontend-oac"
  origin_id                  = "${local.prefix}-frontend-s3"
  bucket_policy_sid          = "AllowCloudFrontOAC"

  aliases             = local.custom_domain ? ["www.${local.domain_name}", local.domain_name] : []
  acm_certificate_arn = module.certificate.certificate_arn

  # Rewrites /about to /about/index.html etc. so prerendered subdirectory HTML resolves from S3.
  # Behind the gate the module associates the gate's function instead, which runs the same
  # appHandler and then checks the session, and this one sits unused.
  viewer_request_function_arn = aws_cloudfront_function.frontend_uri_rewrite.arn

  # cache_mode = "policies" and cache_policy_id = CachingOptimized are the defaults, on every
  # behavior including the SPA shell, which is what the hand-written distribution had.
  origin_request_policy_id   = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf" # CORS-S3Origin
  response_headers_policy_id = "67f7725c-6f97-4210-82d7-5512b31e9d03" # SecurityHeadersPolicy

  distribution_tags = { Name = "${local.prefix}-frontend" }

  access_gate = local.staging_gate_enabled ? {
    key_group_id                                           = module.staging_access_gate[0].key_group_id
    viewer_request_function_arn                            = module.staging_access_gate[0].viewer_request_function_arn
    login_origin_domain_name                               = module.staging_access_gate[0].login_origin_domain_name
    login_origin_access_control_id                         = module.staging_access_gate[0].login_origin_access_control_id
    auth_path_pattern                                      = module.staging_access_gate[0].auth_path_pattern
    cache_policy_id_caching_disabled                       = module.staging_access_gate[0].cache_policy_id_caching_disabled
    origin_request_policy_id_all_viewer_except_host_header = module.staging_access_gate[0].origin_request_policy_id_all_viewer_except_host_header

    # The hand-written login origin id is prefixed; the module default is the bare
    # access-gate-login, so it has to be named here.
    login_origin_id = "${local.prefix}-access-gate-login"
  } : null

  create_dns_records = local.custom_domain
  zone_id            = module.staging_dns.zone_id
  dns_records = {
    www  = "www.${local.domain_name}"
    apex = local.domain_name
  }
}
