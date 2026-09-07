output "aws_account_id" {
  description = "AWS account ID Terraform is deploying into"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region being deployed to"
  value       = data.aws_region.current.name
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidations)"
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_bucket" {
  description = "S3 bucket name for the frontend SPA"
  value       = aws_s3_bucket.frontend.bucket
}

output "domain_name" {
  description = "Domain this environment serves (null without a custom domain)"
  value       = local.custom_domain ? local.domain_name : null
}

output "route53_zone_id" {
  description = "Hosted zone id for domain_name (null without a custom domain)"
  value       = module.staging_dns.zone_id
}

output "route53_zone_name_servers" {
  description = "Name servers of the hosted zone; in staging these are what the parent-zone NS delegation points at"
  value       = module.staging_dns.name_servers
}

output "frontend_url" {
  description = "Public origin of the SPA (custom domain, or the CloudFront hostname)"
  value       = local.frontend_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployments"
  value       = aws_iam_role.github_actions_deploy.arn
}

output "api_invoke_url" {
  description = "HTTP API default execute-api endpoint (disabled while the staging access gate is on)"
  value       = module.api.api_endpoint
}

output "api_url" {
  description = "Public API origin (custom domain, or the execute-api endpoint without one). Use frontend_api_base_url for VITE_API_URL."
  value       = local.api_url
}

output "frontend_api_base_url" {
  description = "Value for VITE_API_URL on the matching GitHub Environment: the site origin while the staging access gate is on (API calls go through CloudFront as /api/*), otherwise api_url"
  value       = local.frontend_api_base_url
}

output "staging_access_gate_hosted_ui" {
  description = "Cognito hosted UI base URL of the staging access gate (null when the gate is off)"
  value       = one(module.staging_access_gate[*].hosted_ui_domain)
}

output "staging_access_gate_user_pool_id" {
  description = "Cognito user pool id of the staging access gate (null when the gate is off)"
  value       = one(module.staging_access_gate[*].user_pool_id)
}

output "lambda_function_name" {
  description = "Lambda API function name"
  value       = aws_lambda_function.api.function_name
}

output "lambda_function_arn" {
  description = "Lambda API function ARN"
  value       = aws_lambda_function.api.arn
}

output "lambda_artifacts_bucket" {
  description = "S3 bucket the deploy workflow uploads Lambda zips to"
  value       = aws_s3_bucket.lambda_artifacts.bucket
}

output "dynamodb_table_names" {
  description = "DynamoDB table names keyed by table suffix"
  value       = { for suffix, table in aws_dynamodb_table.tables : suffix => table.name }
}
