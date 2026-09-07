# ---------------------------------------------------------------------------
# SES Configuration Set
# A properly-named config set for all transactional mail.
# The console-created "my-first-configuration-set" is left unmanaged and can
# be deleted from the AWS console after Terraform associates the domain with
# this one.
# ---------------------------------------------------------------------------
resource "aws_sesv2_configuration_set" "transactional" {
  configuration_set_name = "carmodpicker-transactional"

  reputation_options {
    reputation_metrics_enabled = true
  }

  sending_options {
    sending_enabled = true
  }

  vdm_options {
    dashboard_options {
      engagement_metrics = "ENABLED"
    }
    guardian_options {
      optimized_shared_delivery = "ENABLED"
    }
  }

  tags = { Name = "${local.prefix}-transactional" }
}

# ---------------------------------------------------------------------------
# SES Domain Identity
# carmodpicker.com is already verified in AWS. The three Easy DKIM CNAME
# records are already managed in route53.tf. Keeping the identity in Terraform
# keeps it in sync and associates it with the config set above.
# ---------------------------------------------------------------------------
resource "aws_sesv2_email_identity" "domain" {
  count = local.custom_domain ? 1 : 0

  email_identity         = local.domain_name
  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }

  tags = { Name = "${local.prefix}-ses-domain" }
}

resource "aws_sesv2_email_identity" "sender" {
  count = local.custom_domain ? 0 : 1

  email_identity         = local.email_from
  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name

  tags = { Name = "${local.prefix}-ses-sender" }
}

# ---------------------------------------------------------------------------
# Custom MAIL FROM domain
# Sets the envelope sender to bounce.carmodpicker.com so SPF aligns with
# carmodpicker.com under DMARC (fixes the "MAIL FROM not aligned" warning).
# The matching MX + SPF records are in route53.tf.
# ---------------------------------------------------------------------------
resource "aws_sesv2_email_identity_mail_from_attributes" "domain" {
  count = local.custom_domain ? 1 : 0

  email_identity         = aws_sesv2_email_identity.domain[0].email_identity
  mail_from_domain       = "bounce.${local.domain_name}"
  behavior_on_mx_failure = "USE_DEFAULT_VALUE"
}

# ---------------------------------------------------------------------------
# Feedback forwarding — disabled; SNS event destination handles this instead.
# ---------------------------------------------------------------------------
resource "aws_sesv2_email_identity_feedback_attributes" "domain" {
  count = local.custom_domain ? 1 : 0

  email_identity           = aws_sesv2_email_identity.domain[0].email_identity
  email_forwarding_enabled = false
}

# ---------------------------------------------------------------------------
# SNS topic for SES bounce/complaint/delay notifications → tyler@webbpulse.com
# After apply, AWS will send a subscription confirmation email to that address.
# The event destination will not deliver until the subscription is confirmed.
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "ses_notifications" {
  name = "${local.prefix}-ses-notifications"
  tags = { Name = "${local.prefix}-ses-notifications" }
}

resource "aws_sns_topic_policy" "ses_notifications" {
  arn = aws_sns_topic.ses_notifications.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSESPublish"
      Effect    = "Allow"
      Principal = { Service = "ses.amazonaws.com" }
      Action    = "SNS:Publish"
      Resource  = aws_sns_topic.ses_notifications.arn
      Condition = {
        StringEquals = { "AWS:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "ses_email" {
  topic_arn = aws_sns_topic.ses_notifications.arn
  protocol  = "email"
  endpoint  = "tyler@webbpulse.com"
}

resource "aws_sesv2_configuration_set_event_destination" "sns" {
  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name
  event_destination_name = "sns-notifications"

  event_destination {
    enabled              = true
    matching_event_types = ["BOUNCE", "COMPLAINT", "DELIVERY_DELAY"]

    sns_destination {
      topic_arn = aws_sns_topic.ses_notifications.arn
    }
  }
}

# ---------------------------------------------------------------------------
# Account-level VDM attributes (engagement metrics + optimised delivery).
# ---------------------------------------------------------------------------
resource "aws_sesv2_account_vdm_attributes" "main" {
  vdm_enabled = "ENABLED"

  dashboard_attributes {
    engagement_metrics = "ENABLED"
  }

  guardian_attributes {
    optimized_shared_delivery = "ENABLED"
  }
}
