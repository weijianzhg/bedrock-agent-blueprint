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
# Cloud agent workspace settings
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
  default     = "Cloud agent workspace powered by Strands and AgentCore Runtime"
}

variable "container_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "model_id" {
  description = "Source foundation model or system cross-region inference profile (ID or ARN) for the managed application inference profile"
  type        = string
  default     = "eu.anthropic.claude-sonnet-5"

  validation {
    condition     = trimspace(var.model_id) != "" && !can(regex(":application-inference-profile/", var.model_id))
    error_message = "model_id must select a foundation model or system inference profile, not an application inference profile."
  }
}

variable "inference_profile_tags" {
  description = "Additional cost allocation tags, such as CostCenter or Team. Project, Environment, and Agent are set by Terraform."
  type        = map(string)
  default     = {}
}

variable "log_level" {
  description = "Log level passed to the agent container"
  type        = string
  default     = "INFO"
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
