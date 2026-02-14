variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "agent_name" {
  description = "Name for the AgentCore runtime"
  type        = string
  default     = "bedrock-agent-blueprint"
}

variable "agent_description" {
  description = "Description for the AgentCore runtime"
  type        = string
  default     = "Strands agent deployed via bedrock-agent-blueprint"
}

# --------------------------------------------------------------------------
# Values from infra/platform outputs
# --------------------------------------------------------------------------

variable "ecr_repository_url" {
  description = "ECR repository URL (from infra/platform output)"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN for the AgentCore runtime (from infra/platform output)"
  type        = string
}

# --------------------------------------------------------------------------
# Deployment settings
# --------------------------------------------------------------------------

variable "container_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "network_mode" {
  description = "Network mode for the AgentCore runtime (PUBLIC or VPC)"
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "VPC"], var.network_mode)
    error_message = "network_mode must be either PUBLIC or VPC"
  }
}

variable "log_level" {
  description = "Log level passed to the agent container"
  type        = string
  default     = "INFO"
}
