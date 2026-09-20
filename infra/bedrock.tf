# Keep model_id as the source selector; the runtime always uses the application
# profile so model usage is attributed to this deployment's tags.
data "aws_partition" "current" {}

locals {
  source_is_profile = can(regex("^(us|eu|apac|global)\\.", var.model_id)) || can(regex(":inference-profile/", var.model_id))
  model_source_arn = startswith(var.model_id, "arn:") ? var.model_id : (
    local.source_is_profile
    ? "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.model_id}"
    : "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}::foundation-model/${var.model_id}"
  )
}

data "aws_bedrock_inference_profile" "source" {
  count                = local.source_is_profile ? 1 : 0
  inference_profile_id = local.model_source_arn
}

resource "aws_bedrock_inference_profile" "agent" {
  name        = "${local.name_prefix}-${var.agent_name}"
  description = "Bedrock model cost allocation for this agent deployment"

  model_source {
    copy_from = local.model_source_arn
  }

  tags = merge(var.inference_profile_tags, {
    Project     = var.project_name
    Environment = var.environment
    Agent       = var.agent_name
  })
}
