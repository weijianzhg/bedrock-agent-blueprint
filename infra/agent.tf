# --------------------------------------------------------------------------
# Cloud agent workspace on AgentCore Runtime
# --------------------------------------------------------------------------

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = var.agent_name
  description        = var.agent_description
  role_arn           = aws_iam_role.agentcore_runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent.repository_url}:${var.container_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  # Files survive stop/resume when the caller reuses the same session ID.
  # Storage expires after 14 idle days and resets on runtime version updates.
  filesystem_configuration {
    session_storage {
      mount_path = "/mnt/workspace"
    }
  }

  environment_variables = {
    WORKSPACE_DIR = "/mnt/workspace"
    MODEL_ID      = var.model_id
    LOG_LEVEL     = var.log_level
  }

  depends_on = [
    aws_iam_role_policy.ecr_pull,
    aws_iam_role_policy.bedrock_invoke,
    aws_iam_role_policy.cloudwatch_logs,
  ]
}
