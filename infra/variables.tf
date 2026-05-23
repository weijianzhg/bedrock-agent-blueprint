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
  description = "Name for the AgentCore runtime (alphanumeric and underscores only)"
  type        = string
  default     = "bedrock_agent_blueprint"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,47}$", var.agent_name))
    error_message = "agent_name must start with a letter, contain only alphanumeric characters and underscores, and be at most 48 characters."
  }
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

# --------------------------------------------------------------------------
# Optional AgentCore Memory
# --------------------------------------------------------------------------

variable "agent_memory_enabled" {
  description = "Whether to create AgentCore Memory resources and expose their IDs to the runtime"
  type        = bool
  default     = true
}

variable "agent_memory_name" {
  description = "Optional explicit AgentCore Memory name. Defaults to a sanitized project/environment name."
  type        = string
  default     = null
}

variable "agent_memory_namespace" {
  description = "Namespace used for semantic memory records"
  type        = string
  default     = "agent-memory"
}

variable "agent_memory_event_expiry_days" {
  description = "Number of days AgentCore Memory events are retained"
  type        = number
  default     = 90

  validation {
    condition     = var.agent_memory_event_expiry_days >= 1
    error_message = "agent_memory_event_expiry_days must be at least 1."
  }
}

# --------------------------------------------------------------------------
# Optional GitHub Actions OIDC role
# --------------------------------------------------------------------------

variable "github_actions_oidc_enabled" {
  description = "Whether Terraform should create an IAM role for GitHub Actions OIDC deployments"
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the deploy role, in owner/repo form"
  type        = string
  default     = ""
}

variable "github_oidc_provider_arn" {
  description = "Optional existing GitHub Actions OIDC provider ARN. Leave empty to create one when github_actions_oidc_enabled is true."
  type        = string
  default     = ""
}

variable "github_deploy_branch" {
  description = "Branch allowed to assume the deploy role"
  type        = string
  default     = "main"
}

variable "terraform_state_bucket" {
  description = "Optional S3 bucket used by CI for Terraform state. Required only when granting CI state access."
  type        = string
  default     = ""
}

variable "terraform_state_key" {
  description = "Optional S3 key used by CI for Terraform state. Required only when granting CI state access."
  type        = string
  default     = ""
}
