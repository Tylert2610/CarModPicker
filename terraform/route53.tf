# The hosted zone and, in staging, its NS delegation into the parent zone in the production
# account come from the shared platform module. Production creates the carmodpicker.com zone
# itself (delegate = false, the registrar holds those NS records); staging creates
# staging.carmodpicker.com and delegates it.
module "staging_dns" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/staging-dns"
  version = "~> 1.3"

  providers = {
    aws        = aws
    aws.parent = aws.parent_dns
  }

  enabled        = local.custom_domain
  zone_name      = local.domain_name
  delegate       = local.parent_delegation
  parent_zone_id = var.parent_route53_zone_id
}

# Apex to CloudFront (redirect to www is done by the CloudFront viewer-request
# function so we don't need a separate S3 website bucket to handle it).
resource "aws_route53_record" "apex_a" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = local.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# www to the CloudFront distribution
resource "aws_route53_record" "www" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = "www.${local.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# Apex TXT records. Route53 stores all TXT records at the same name in a
# single RRSet, so SPF and domain-verification strings share one resource.
resource "aws_route53_record" "spf" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = local.domain_name
  type    = "TXT"
  ttl     = 300
  records = [
    "v=spf1 include:amazonses.com ~all",
    "google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8",
  ]
}

# Google Search Console domain ownership verification for www.carmodpicker.com
resource "aws_route53_record" "www_google_site_verification" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = "www.${local.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8"]
}

# SES DKIM verification records
resource "aws_route53_record" "ses_dkim" {
  count   = local.custom_domain ? 3 : 0
  zone_id = module.staging_dns.zone_id
  name    = "${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}._domainkey.${local.domain_name}"
  type    = "CNAME"
  ttl     = 60
  records = ["${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

# Custom MAIL FROM domain records (SPF alignment for DMARC)
resource "aws_route53_record" "ses_mail_from_mx" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = "bounce.${local.domain_name}"
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.${var.aws_region}.amazonses.com"]
}

resource "aws_route53_record" "ses_mail_from_spf" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = "bounce.${local.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}

# DMARC policy record
resource "aws_route53_record" "dmarc" {
  count = local.custom_domain ? 1 : 0

  zone_id = module.staging_dns.zone_id
  name    = "_dmarc.${local.domain_name}"
  type    = "TXT"
  ttl     = 60
  records = ["v=DMARC1; p=none;"]
}
