mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/test-runtime" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_bedrock_inference_profile" {
    defaults = {
      models = [
        { model_arn = "arn:aws:bedrock:eu-west-1::foundation-model/anthropic.claude-sonnet-5" },
        { model_arn = "arn:aws:bedrock:eu-west-3::foundation-model/anthropic.claude-sonnet-5" },
      ]
    }
  }
  mock_resource "aws_bedrock_inference_profile" {
    defaults = {
      arn    = "arn:aws:bedrock:eu-west-1:123456789012:application-inference-profile/testprofile"
      models = [{ model_arn = "arn:aws:bedrock:eu-west-1::foundation-model/anthropic.claude-sonnet-5" }]
    }
  }
}

run "cross_region_cost_allocation" {
  command = apply
  variables {
    inference_profile_tags = { CostCenter = "engineering", Project = "must-not-override" }
  }
  assert {
    condition     = aws_bedrock_inference_profile.agent[0].model_source[0].copy_from == "arn:aws:bedrock:eu-west-1:123456789012:inference-profile/eu.anthropic.claude-sonnet-5"
    error_message = "Cross-region IDs must resolve to account-scoped system profile ARNs."
  }
  assert {
    condition     = aws_bedrockagentcore_agent_runtime.this.environment_variables["MODEL_ID"] == aws_bedrock_inference_profile.agent[0].arn
    error_message = "Runtime invocations must use the managed application profile."
  }
  assert {
    condition     = length(aws_bedrockagentcore_agent_runtime.this.protocol_configuration) == 0 && length(aws_bedrockagentcore_agent_runtime.this.filesystem_configuration) == 1
    error_message = "Agents keep the default HTTP protocol and managed session storage."
  }
  assert {
    condition     = aws_bedrock_inference_profile.agent[0].tags["Project"] == var.project_name && aws_bedrock_inference_profile.agent[0].tags["Environment"] == var.environment && aws_bedrock_inference_profile.agent[0].tags["Agent"] == var.agent_name && aws_bedrock_inference_profile.agent[0].tags["CostCenter"] == "engineering"
    error_message = "Allocation tags must include fixed deployment identity and custom tags."
  }
  assert {
    condition = alltrue([
      for statement in data.aws_iam_policy_document.bedrock_invoke[0].statement : (
        toset(statement.resources) == toset([aws_bedrock_inference_profile.agent[0].arn]) || (
          length(statement.condition) == 1 && alltrue([
            for condition in statement.condition : condition.test == "StringEquals" && condition.variable == "bedrock:InferenceProfileArn" && toset(condition.values) == toset([aws_bedrock_inference_profile.agent[0].arn])
          ])
        )
      ) if contains(statement.actions, "bedrock:InvokeModel") || contains(statement.actions, "bedrock:InvokeModelWithResponseStream")
    ])
    error_message = "Backing-model invocation must require the managed application profile, preventing unallocated direct calls."
  }
  assert {
    condition = alltrue([
      for model in aws_bedrock_inference_profile.agent[0].models : contains(
        one([for statement in data.aws_iam_policy_document.bedrock_invoke[0].statement : statement.resources if statement.sid == "InvokeProfileModels"]),
        model.model_arn,
      )
    ])
    error_message = "Runtime IAM must allow every backing model in the application profile."
  }
}

run "mcp_without_ci_has_no_model_lookup" {
  command = plan
  variables {
    runtime_type                = "mcp"
    github_actions_oidc_enabled = false
    # The default EU model must not require a lookup in this deployment region.
    aws_region = "us-east-1"
  }
  assert {
    condition     = length(data.aws_bedrock_inference_profile.source) == 0
    error_message = "MCP without CI must not look up a Bedrock model profile."
  }
}

run "mcp_server_has_no_model_access" {
  command = plan
  variables {
    runtime_type                = "mcp"
    github_actions_oidc_enabled = true
    github_repository           = "example/blueprint"
    github_oidc_provider_arn    = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
  }
  assert {
    condition     = one(aws_bedrockagentcore_agent_runtime.this.protocol_configuration[*].server_protocol) == "MCP"
    error_message = "MCP servers must use the MCP server protocol."
  }
  assert {
    condition     = length(aws_bedrockagentcore_agent_runtime.this.filesystem_configuration) == 0 && toset(keys(aws_bedrockagentcore_agent_runtime.this.environment_variables)) == toset(["LOG_LEVEL"])
    error_message = "MCP servers get no session storage, workspace, or model settings."
  }
  assert {
    condition     = length(aws_bedrock_inference_profile.agent) == 0 && length(aws_iam_role_policy.bedrock_invoke) == 0
    error_message = "MCP servers must not get an inference profile or Bedrock invoke permissions."
  }
  assert {
    condition     = contains([for statement in data.aws_iam_policy_document.ci_deploy[0].statement : statement.sid], "CreateApplicationInferenceProfiles")
    error_message = "CI keeps profile permissions so an MCP deployment can switch back to an agent."
  }
  assert {
    condition = alltrue([
      for model in data.aws_bedrock_inference_profile.source[0].models : contains(
        one([for statement in data.aws_iam_policy_document.ci_deploy[0].statement : statement.resources if statement.sid == "CreateApplicationInferenceProfiles"]),
        model.model_arn,
      )
    ])
    error_message = "MCP deployments with CI must retain permissions for every source model so CI can switch back to an agent."
  }
}

run "reject_unknown_runtime_type" {
  command = plan
  variables { runtime_type = "a2a" }
  expect_failures = [var.runtime_type]
}

run "foundation_model_id" {
  command = plan
  variables { model_id = "amazon.nova-lite-v1:0" }
  assert {
    condition     = local.model_source_arn == "arn:aws:bedrock:eu-west-1::foundation-model/amazon.nova-lite-v1:0" && !local.source_is_profile
    error_message = "Foundation model IDs must resolve without an account ID."
  }
}

run "ci_can_create_cross_region_profiles" {
  command = plan
  variables {
    github_actions_oidc_enabled = true
    github_repository           = "example/blueprint"
    github_oidc_provider_arn    = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
  }
  assert {
    condition = alltrue([
      for arn in data.aws_bedrock_inference_profile.source[0].models : contains(
        one([for statement in data.aws_iam_policy_document.ci_deploy[0].statement : statement.resources if statement.sid == "CreateApplicationInferenceProfiles"]),
        arn.model_arn,
      )
    ])
    error_message = "CI needs CreateInferenceProfile permission on every destination foundation model."
  }
}

run "explicit_system_profile_arn" {
  command = plan
  variables { model_id = "arn:aws:bedrock:eu-west-1:123456789012:inference-profile/eu.amazon.nova-lite-v1:0" }
  assert {
    condition     = local.model_source_arn == var.model_id && local.source_is_profile
    error_message = "Explicit system profile ARNs must be preserved and granted backing-profile access."
  }
}

run "explicit_foundation_model_arn" {
  command = plan
  variables { model_id = "arn:aws:bedrock:eu-west-1::foundation-model/amazon.nova-lite-v1:0" }
  assert {
    condition     = local.model_source_arn == var.model_id && !local.source_is_profile
    error_message = "Explicit foundation model ARNs must be preserved."
  }
}

run "reject_application_profile_source" {
  command = plan
  variables { model_id = "arn:aws:bedrock:eu-west-1:123456789012:application-inference-profile/existing" }
  expect_failures = [var.model_id]
}

run "long_agent_name_has_valid_profile_name" {
  command = plan
  variables { agent_name = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuv" }
  assert {
    condition     = length(aws_bedrock_inference_profile.agent[0].name) <= 64 && can(regex("^([0-9a-zA-Z][ _-]?)+$", aws_bedrock_inference_profile.agent[0].name))
    error_message = "A supported 48-character agent name must produce a valid Bedrock profile name."
  }
}

run "repeated_underscores_have_valid_profile_name" {
  command = plan
  variables { agent_name = "agent__workspace_" }
  assert {
    condition     = can(regex("^([0-9a-zA-Z][ _-]?)+$", aws_bedrock_inference_profile.agent[0].name))
    error_message = "AgentCore allows repeated underscores but Bedrock profile names do not."
  }
}
