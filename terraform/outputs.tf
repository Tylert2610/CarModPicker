output "aws_account_id" {
  description = "AWS account ID Terraform is deploying into"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region being deployed to"
  value       = data.aws_region.current.region
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = module.frontend.distribution_domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidations)"
  value       = module.frontend.distribution_id
}

output "frontend_bucket" {
  description = "S3 bucket name for the frontend SPA"
  value       = module.frontend.bucket_name
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
  value       = module.github_actions_role.role_arn
}

output "github_actions_ci_role_arn" {
  description = "IAM role ARN for pull request CI: read only CodeArtifact access, no deploy permissions. Set it as the CI_AWS_ROLE_ARN repository variable, taking the staging workspace's value since pull request checks resolve the same read only package either way."
  value       = module.github_actions_ci_role.role_arn
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
  description = "Value for VITE_API_URL on the matching GitHub Environment: the API host in every environment, staging access gate included"
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
  value       = module.lambda_api.function_name
}

output "lambda_function_arn" {
  description = "Lambda API function ARN"
  value       = module.lambda_api.function_arn
}

output "lambda_artifacts_bucket" {
  description = "S3 bucket the deploy workflow uploads Lambda zips to"
  value       = module.lambda_artifacts.bucket_id
}

output "dynamodb_table_names" {
  description = "DynamoDB table names keyed by table suffix"
  value       = module.dynamodb.table_names
}
