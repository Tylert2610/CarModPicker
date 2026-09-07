# State moves. Everything here is a rename of an object Terraform already manages: no resource is
# created, changed or destroyed by any of these blocks.
#
# The first group is the older count-conversion chain (a bare resource became resource[0]). Those
# moves were applied long ago in both workspaces, but they are kept because Terraform follows the
# chain from the original address into the module addresses below.

moved {
  from = aws_route53_record.spf
  to   = aws_route53_record.spf[0]
}

moved {
  from = aws_route53_record.www_google_site_verification
  to   = aws_route53_record.www_google_site_verification[0]
}

moved {
  from = aws_route53_record.ses_dkim_1
  to   = aws_route53_record.ses_dkim[0]
}

moved {
  from = aws_route53_record.ses_dkim_2
  to   = aws_route53_record.ses_dkim[1]
}

moved {
  from = aws_route53_record.ses_dkim_3
  to   = aws_route53_record.ses_dkim[2]
}

moved {
  from = aws_route53_record.ses_mail_from_mx
  to   = aws_route53_record.ses_mail_from_mx[0]
}

moved {
  from = aws_route53_record.ses_mail_from_spf
  to   = aws_route53_record.ses_mail_from_spf[0]
}

moved {
  from = aws_route53_record.dmarc
  to   = aws_route53_record.dmarc[0]
}

moved {
  from = aws_acm_certificate.carmodpicker
  to   = aws_acm_certificate.carmodpicker[0]
}

moved {
  from = aws_acm_certificate_validation.carmodpicker
  to   = aws_acm_certificate_validation.carmodpicker[0]
}

# ---------------------------------------------------------------------------
# staging-dns
# ---------------------------------------------------------------------------

moved {
  from = aws_route53_zone.carmodpicker
  to   = aws_route53_zone.carmodpicker[0]
}

moved {
  from = aws_route53_zone.carmodpicker[0]
  to   = module.staging_dns.aws_route53_zone.this[0]
}

moved {
  from = aws_route53_record.parent_delegation[0]
  to   = module.staging_dns.aws_route53_record.delegation[0]
}

# ---------------------------------------------------------------------------
# http-api
# ---------------------------------------------------------------------------

moved {
  from = aws_apigatewayv2_api.api
  to   = module.api.aws_apigatewayv2_api.this
}

moved {
  from = aws_cloudwatch_log_group.api_access
  to   = module.api.aws_cloudwatch_log_group.access
}

moved {
  from = aws_apigatewayv2_integration.lambda
  to   = module.api.aws_apigatewayv2_integration.lambda
}

moved {
  from = aws_apigatewayv2_route.default
  to   = module.api.aws_apigatewayv2_route.this["$default"]
}

moved {
  from = aws_apigatewayv2_stage.default
  to   = module.api.aws_apigatewayv2_stage.default
}

moved {
  from = aws_lambda_permission.api
  to   = module.api.aws_lambda_permission.api
}

moved {
  from = aws_apigatewayv2_domain_name.api
  to   = module.api.aws_apigatewayv2_domain_name.this
}

moved {
  from = aws_apigatewayv2_api_mapping.api
  to   = module.api.aws_apigatewayv2_api_mapping.this
}

moved {
  from = aws_route53_record.api_lambda
  to   = module.api.aws_route53_record.alias
}

# ---------------------------------------------------------------------------
# spa-frontend
# ---------------------------------------------------------------------------

moved {
  from = aws_s3_bucket.frontend
  to   = module.frontend.aws_s3_bucket.this
}

moved {
  from = aws_s3_bucket_public_access_block.frontend
  to   = module.frontend.aws_s3_bucket_public_access_block.this
}

moved {
  from = aws_s3_bucket_policy.frontend
  to   = module.frontend.aws_s3_bucket_policy.this
}

moved {
  from = aws_cloudfront_origin_access_control.frontend
  to   = module.frontend.aws_cloudfront_origin_access_control.this
}

moved {
  from = aws_cloudfront_distribution.frontend
  to   = module.frontend.aws_cloudfront_distribution.this
}

moved {
  from = aws_route53_record.apex_a
  to   = aws_route53_record.apex_a[0]
}

moved {
  from = aws_route53_record.apex_a[0]
  to   = module.frontend.aws_route53_record.alias_a["apex"]
}

moved {
  from = aws_route53_record.www
  to   = aws_route53_record.www[0]
}

moved {
  from = aws_route53_record.www[0]
  to   = module.frontend.aws_route53_record.alias_a["www"]
}
