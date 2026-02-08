output "ecr_repository_url" {
  description = "ECR repository URL — pass to build_and_push.sh and infra/agent"
  value       = aws_ecr_repository.agent.repository_url
}

output "role_arn" {
  description = "IAM role ARN for the AgentCore runtime"
  value       = aws_iam_role.agentcore_runtime.arn
}
