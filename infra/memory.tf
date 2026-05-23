# --------------------------------------------------------------------------
# AgentCore Memory
#
# Optional long-term memory for reusable agent facts, decisions, summaries, or
# run metadata. The Python helper in agents/memory.py writes both an event and a
# directly queryable semantic memory record.
# --------------------------------------------------------------------------

locals {
  default_agent_memory_name = substr(replace("${local.name_prefix}-memory", "-", "_"), 0, 48)
  agent_memory_name         = coalesce(var.agent_memory_name, local.default_agent_memory_name)
}

resource "aws_bedrockagentcore_memory" "this" {
  count = var.agent_memory_enabled ? 1 : 0

  name                  = local.agent_memory_name
  description           = "Long-term memory for agent facts, decisions, summaries, and operational metadata."
  event_expiry_duration = var.agent_memory_event_expiry_days
}

resource "aws_bedrockagentcore_memory_strategy" "semantic" {
  count = var.agent_memory_enabled ? 1 : 0

  name        = "semantic_memory"
  memory_id   = aws_bedrockagentcore_memory.this[0].id
  type        = "SEMANTIC"
  description = "Semantic lookup for durable agent memory records."
  namespaces  = [var.agent_memory_namespace]
}
