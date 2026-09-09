output "ecr_repository_url" {
  description = "ECR repository URL — used by build_and_push.sh"
  value       = aws_ecr_repository.agent.repository_url
}

output "role_arn" {
  description = "IAM role ARN for the AgentCore runtime"
  value       = aws_iam_role.agentcore_runtime.arn
}

output "agent_runtime_arn" {
  description = "ARN of the deployed AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "Unique ID of the AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

output "ci_deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployments, when enabled"
  value       = var.github_actions_oidc_enabled ? aws_iam_role.ci_deploy[0].arn : null
}
