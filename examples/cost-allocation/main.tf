# Account-wide billing settings: use a separate state owned by the billing
# administrator, not one copy per agent deployment.
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.46.0, < 7.0.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "tag_keys" {
  description = "Existing billing tag keys to activate after AWS has discovered the resource tags"
  type        = set(string)
  default     = ["Project", "Environment", "Agent"]
}

resource "aws_ce_cost_allocation_tag" "agent" {
  for_each = var.tag_keys
  tag_key  = each.value
  status   = "Active"

  lifecycle {
    prevent_destroy = true
  }
}
