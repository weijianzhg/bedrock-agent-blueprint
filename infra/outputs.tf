output "agent_runtime_arn" {
  description = "ARN of the deployed AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "Unique ID of the AgentCore runtime"
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
}

output "ecr_repository_url" {
  description = "ECR repository URL — use this in build_and_push.sh"
  value       = aws_ecr_repository.agent.repository_url
}

output "iam_role_arn" {
  description = "ARN of the IAM role used by the AgentCore runtime"
  value       = aws_iam_role.agentcore_runtime.arn
}
