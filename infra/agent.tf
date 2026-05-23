# --------------------------------------------------------------------------
# AgentCore Runtime
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
    network_mode = var.network_mode
  }

  environment_variables = {
    LOG_LEVEL = var.log_level
    AGENTCORE_MEMORY_ID = (
      var.agent_memory_enabled ? aws_bedrockagentcore_memory.this[0].id : ""
    )
    AGENTCORE_MEMORY_STRATEGY_ID = (
      var.agent_memory_enabled ? aws_bedrockagentcore_memory_strategy.semantic[0].memory_strategy_id : ""
    )
    AGENTCORE_MEMORY_NAMESPACE = var.agent_memory_namespace
  }
}
