# --------------------------------------------------------------------------
# ECR Repository for agent container images
#
# The build_and_push.sh script creates this repository via AWS CLI on its
# first run (before Terraform has been applied).  The import block below
# adopts the existing repository into Terraform state so it can be managed
# and torn down with `terraform destroy`.
# --------------------------------------------------------------------------

import {
  to = aws_ecr_repository.agent
  id = "${var.project_name}-${var.environment}"
}

resource "aws_ecr_repository" "agent" {
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the last 10 untagged images to avoid runaway storage costs.
resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 10 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
