# CloudFront requires ACM certificates in us-east-1; the API Gateway custom domain needs a
# regional one. Both come from the shared acm-certificate module, which also writes the
# DNS validation records into the zone.
module "certificate" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/acm-certificate"
  version = "~> 1.6"

  providers = {
    aws         = aws.us_east_1
    aws.records = aws
  }

  enabled     = local.custom_domain
  domain_name = local.domain_name
  subject_alternative_names = [
    "*.${local.domain_name}",
  ]
  zone_id = module.staging_dns.zone_id

  depends_on = [module.staging_dns]
}

module "api_certificate" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/acm-certificate"
  version = "~> 1.6"

  providers = {
    aws         = aws
    aws.records = aws
  }

  enabled     = local.custom_domain
  domain_name = "api.${local.domain_name}"
  zone_id     = module.staging_dns.zone_id

  depends_on = [module.staging_dns]
}

moved {
  from = aws_acm_certificate.carmodpicker[0]
  to   = module.certificate.aws_acm_certificate.this[0]
}

moved {
  from = aws_route53_record.acm_validation
  to   = module.certificate.aws_route53_record.validation
}

moved {
  from = aws_acm_certificate_validation.carmodpicker[0]
  to   = module.certificate.aws_acm_certificate_validation.this[0]
}

moved {
  from = aws_acm_certificate.api[0]
  to   = module.api_certificate.aws_acm_certificate.this[0]
}

moved {
  from = aws_route53_record.acm_api_validation
  to   = module.api_certificate.aws_route53_record.validation
}

moved {
  from = aws_acm_certificate_validation.api[0]
  to   = module.api_certificate.aws_acm_certificate_validation.this[0]
}
