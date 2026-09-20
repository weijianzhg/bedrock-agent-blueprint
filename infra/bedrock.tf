# Keep model_id as the source selector; the runtime always uses the application
# profile so model usage is attributed to this deployment's tags.
data "aws_partition" "current" {}

locals {
  # Bedrock permits at most 64 characters and single separators. AgentCore
  # permits longer combined names and repeated underscores. Preserve readable
  # names when valid; otherwise sanitize and hash the full identity to avoid
  # collisions caused by truncation or separator normalization.
  inference_profile_full_name = "${local.name_prefix}-${var.agent_name}"
  inference_profile_name = (
    length(local.inference_profile_full_name) <= 64 && can(regex("^([0-9a-zA-Z][ _-]?)+$", local.inference_profile_full_name))
    ? local.inference_profile_full_name
    : "${trim(substr(replace(local.inference_profile_full_name, "/[^0-9A-Za-z]+/", "-"), 0, 51), "-")}-${substr(sha256(local.inference_profile_full_name), 0, 12)}"
  )

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
  name        = local.inference_profile_name
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
