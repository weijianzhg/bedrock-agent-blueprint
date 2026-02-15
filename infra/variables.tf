variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used to prefix resource names"
  type        = string
  default     = "bedrock-agent-blueprint"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod"
  }
}

# --------------------------------------------------------------------------
# Agent settings
# --------------------------------------------------------------------------

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
