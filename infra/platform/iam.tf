# --------------------------------------------------------------------------
# IAM Role for AgentCore Runtime
# --------------------------------------------------------------------------

data "aws_iam_policy_document" "agentcore_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agentcore_runtime" {
  name               = "${var.project_name}-${var.environment}-runtime"
  assume_role_policy = data.aws_iam_policy_document.agentcore_assume_role.json
}

# --------------------------------------------------------------------------
# ECR Pull — allow the runtime to pull container images
# --------------------------------------------------------------------------

data "aws_iam_policy_document" "ecr_pull" {
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.agent.arn]
  }
}

resource "aws_iam_role_policy" "ecr_pull" {
  name   = "ecr-pull"
  role   = aws_iam_role.agentcore_runtime.id
  policy = data.aws_iam_policy_document.ecr_pull.json
}

# --------------------------------------------------------------------------
# Bedrock Model Invocation — allow the agent to call foundation models
# --------------------------------------------------------------------------

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:inference-profile/*",
    ]
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.agentcore_runtime.id
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}

# --------------------------------------------------------------------------
# CloudWatch Logs — allow the runtime to write logs and metrics
# --------------------------------------------------------------------------

data "aws_iam_policy_document" "cloudwatch_logs" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/*",
    ]
  }
}

resource "aws_iam_role_policy" "cloudwatch_logs" {
  name   = "cloudwatch-logs"
  role   = aws_iam_role.agentcore_runtime.id
  policy = data.aws_iam_policy_document.cloudwatch_logs.json
}
