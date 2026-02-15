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
