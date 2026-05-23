# --------------------------------------------------------------------------
# Optional GitHub Actions OIDC deploy role
#
# Enable with github_actions_oidc_enabled = true and set github_repository to
# "owner/repo". The workflow uses this role through the AWS_ROLE_TO_ASSUME
# repository secret.
# --------------------------------------------------------------------------

locals {
  ci_state_configured = (
    trimspace(var.terraform_state_bucket) != "" &&
    trimspace(var.terraform_state_key) != ""
  )
  create_github_oidc_provider = (
    var.github_actions_oidc_enabled &&
    trimspace(var.github_oidc_provider_arn) == ""
  )
  github_oidc_provider_arn = (
    trimspace(var.github_oidc_provider_arn) != ""
    ? var.github_oidc_provider_arn
    : try(aws_iam_openid_connect_provider.github_actions[0].arn, "")
  )
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  count = local.create_github_oidc_provider ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "ci_deploy_assume_role" {
  count = var.github_actions_oidc_enabled ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/${var.github_deploy_branch}"]
    }
  }
}

resource "aws_iam_role" "ci_deploy" {
  count = var.github_actions_oidc_enabled ? 1 : 0

  name               = "${local.name_prefix}-ci-deploy"
  assume_role_policy = data.aws_iam_policy_document.ci_deploy_assume_role[0].json
}

data "aws_iam_policy_document" "ci_deploy" {
  count = var.github_actions_oidc_enabled ? 1 : 0

  dynamic "statement" {
    for_each = local.ci_state_configured ? [1] : []

    content {
      sid    = "TerraformStateBucket"
      effect = "Allow"
      actions = [
        "s3:GetBucketLocation",
        "s3:ListBucket",
      ]
      resources = ["arn:aws:s3:::${var.terraform_state_bucket}"]
    }
  }

  dynamic "statement" {
    for_each = local.ci_state_configured ? [1] : []

    content {
      sid    = "TerraformStateObjects"
      effect = "Allow"
      actions = [
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:PutObject",
      ]
      resources = [
        "arn:aws:s3:::${var.terraform_state_bucket}/${var.terraform_state_key}",
        "arn:aws:s3:::${var.terraform_state_bucket}/${var.terraform_state_key}.tflock",
      ]
    }
  }

  statement {
    sid    = "EcrReadWrite"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:CreateRepository",
      "ecr:DeleteLifecyclePolicy",
      "ecr:DeleteRepository",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:GetLifecyclePolicy",
      "ecr:InitiateLayerUpload",
      "ecr:ListTagsForResource",
      "ecr:PutImage",
      "ecr:PutImageScanningConfiguration",
      "ecr:PutImageTagMutability",
      "ecr:PutLifecyclePolicy",
      "ecr:TagResource",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.agent.arn]
  }

  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "ManageAgentCore"
    effect = "Allow"
    actions = [
      "bedrock-agentcore:*",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ManageRuntimeIam"
    effect = "Allow"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name_prefix}-runtime",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name_prefix}-ci-deploy",
    ]
  }

  statement {
    sid     = "CreateAgentCoreServiceLinkedRole"
    effect  = "Allow"
    actions = ["iam:CreateServiceLinkedRole"]
    resources = [
      "arn:aws:iam::*:role/aws-service-role/bedrock-agentcore.amazonaws.com/AWSServiceRoleForBedrockAgentCoreGatewayNetwork",
      "arn:aws:iam::*:role/aws-service-role/identity-network.bedrock-agentcore.amazonaws.com/AWSServiceRoleForBedrockAgentCoreIdentity",
      "arn:aws:iam::*:role/aws-service-role/network.bedrock-agentcore.amazonaws.com/AWSServiceRoleForBedrockAgentCoreNetwork",
      "arn:aws:iam::*:role/aws-service-role/runtime-identity.bedrock-agentcore.amazonaws.com/AWSServiceRoleForBedrockAgentCoreRuntimeIdentity",
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values = [
        "bedrock-agentcore.amazonaws.com",
        "identity-network.bedrock-agentcore.amazonaws.com",
        "network.bedrock-agentcore.amazonaws.com",
        "runtime-identity.bedrock-agentcore.amazonaws.com",
      ]
    }
  }

  statement {
    sid    = "ManageGithubOidcProvider"
    effect = "Allow"
    actions = [
      "iam:GetOpenIDConnectProvider",
      "iam:ListOpenIDConnectProviders",
      "iam:TagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = [local.github_oidc_provider_arn]
  }

  statement {
    sid       = "ReadAccountContext"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ci_deploy" {
  count = var.github_actions_oidc_enabled ? 1 : 0

  name   = "ci-deploy"
  role   = aws_iam_role.ci_deploy[0].id
  policy = data.aws_iam_policy_document.ci_deploy[0].json
}
