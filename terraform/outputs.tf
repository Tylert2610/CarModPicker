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

# ---------------------------------------------------------------------------
# The per-domain functions from lambda_domains.tf. Both maps carry only the
# domains whose function exists, which is `media` today and grows by one with
# each of rows 18 through 31, so a consumer reading either one is reading the
# truth about this environment rather than the nine names the plan will
# eventually reach.
# ---------------------------------------------------------------------------

output "domain_lambda_function_names" {
  description = "Per-domain Lambda function name keyed by domain. This is the key deploy-backend.yml builds its function-image map on, and the name its existing-functions job probes with get-function-configuration before handing the map to UpdateFunctionCode."
  value       = { for name, fn in module.lambda_domain : name => fn.function_name }
}

output "domain_lambda_function_arns" {
  description = "Per-domain Lambda function ARN keyed by domain. Row 14's API Gateway integrations and the alarm module's function list in row 15 both read this rather than rebuilding the ARN from the account id and the region."
  value       = { for name, fn in module.lambda_domain : name => fn.function_arn }
}

output "domain_lambda_log_group_names" {
  description = "Per-domain CloudWatch log group name keyed by domain. Row 15 merges these into the alarm module's error_log_groups, and a responder tailing one domain does not have to guess the group from the function name."
  value       = { for name, fn in module.lambda_domain : name => fn.log_group_name }
}

# ---------------------------------------------------------------------------
# The event plumbing from row 22. Nothing consumes these yet; they exist so the
# seams in rows 24, 25, 28 and 30 have something to name.
# ---------------------------------------------------------------------------

output "dynamodb_stream_arns" {
  description = "Latest stream ARN keyed by table, for the four streamed tables only. This is what an event source mapping's event_source_arn takes in rows 24 and 25. A table without a stream is absent rather than null, so a consumer indexing this map fails at plan time on a table that was never streamed rather than passing null to the mapping."
  value       = { for name in keys(local.dynamodb_stream_view_types) : name => module.dynamodb.stream_arns[name] }
}

output "stream_consumer_dlq_arns" {
  description = "Stream consumer dead letter queue ARN keyed by table. This is what an event source mapping's on_failure destination_config takes: the mapping writes the metadata of a batch it could not process here after its retries are spent."
  value       = { for key, q in aws_sqs_queue.stream_dlq : key => q.arn }
}

output "work_queue_arns" {
  description = "Work queue ARN keyed by job, for the two asynchronous seams. part-purge is row 28 and user-delete is row 30."
  value       = { for key, q in aws_sqs_queue.work : key => q.arn }
}

output "work_queue_urls" {
  description = "Work queue URL keyed by job. A producer sends with the URL rather than the ARN, so the tombstone writer in rows 28 and 30 reads this one."
  value       = { for key, q in aws_sqs_queue.work : key => q.url }
}

output "work_queue_dlq_arns" {
  description = "Work queue dead letter queue ARN keyed by job. Named by the redrive policy on the queue itself, so a consumer needs this only to drain one by hand."
  value       = { for key, q in aws_sqs_queue.work_dlq : key => q.arn }
}
