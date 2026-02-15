#!/usr/bin/env bash
# -------------------------------------------------------------------
# Build the agent Docker image (ARM64) and push it to ECR.
#
# Usage:
#   ./scripts/build_and_push.sh
#
# Prerequisites:
#   - Docker (with buildx) or Finch
#   - AWS CLI configured with appropriate credentials
#
# On first run the script creates the ECR repository automatically.
# -------------------------------------------------------------------

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/agents"
INFRA_DIR="${ROOT_DIR}/infra"
TFVARS_FILE="${INFRA_DIR}/terraform.tfvars"

# ---- Resolve AWS account and region ----
AWS_REGION=$(aws configure get region 2>/dev/null || echo "eu-west-1")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# ---- Resolve ECR repository URL ----
# Fast path: read from Terraform state (works after the first full apply).
# Validate with a pattern match because `terraform output` may print warnings
# to stdout (e.g. after destroy) instead of returning a non-zero exit code.
ECR_URL=$(terraform -chdir="$INFRA_DIR" output -no-color -raw ecr_repository_url 2>/dev/null || true)
if [[ ! "$ECR_URL" =~ \.dkr\.ecr\. ]]; then
  ECR_URL=""
fi

if [ -z "$ECR_URL" ]; then
  # First run — Terraform hasn't been applied yet.  Derive the repo name
  # from terraform.tfvars (or fall back to defaults) and create the repo.
  if [ -f "$TFVARS_FILE" ]; then
    PROJECT_NAME=$(awk -F'"' '/^[[:space:]]*project_name[[:space:]]*=/{print $2; exit}' "$TFVARS_FILE")
    ENVIRONMENT=$(awk -F'"' '/^[[:space:]]*environment[[:space:]]*=/{print $2; exit}' "$TFVARS_FILE")
  fi
  PROJECT_NAME="${PROJECT_NAME:-bedrock-agent-blueprint}"
  ENVIRONMENT="${ENVIRONMENT:-dev}"
  REPO_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

  echo "ECR repository not found in Terraform state."
  echo "Ensuring ECR repository exists: ${REPO_NAME} ..."

  # create-repository is idempotent-ish: ignore RepositoryAlreadyExistsException
  aws ecr create-repository \
    --repository-name "$REPO_NAME" \
    --image-tag-mutability MUTABLE \
    --image-scanning-configuration scanOnPush=true \
    --region "$AWS_REGION" 2>/dev/null || true

  ECR_URL="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}"
fi

TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD)}"
IMAGE_URI="${ECR_URL}:${TAG}"
LATEST_URI="${ECR_URL}:latest"

echo ""
echo "Agent directory : ${AGENT_DIR}"
echo "ECR image URI   : ${IMAGE_URI}"
echo ""

# Authenticate with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Build ARM64 image and push both the versioned tag and latest
echo "Building ARM64 image..."
docker buildx build \
  --platform linux/arm64 \
  -f "${AGENT_DIR}/Dockerfile" \
  -t "${IMAGE_URI}" \
  -t "${LATEST_URI}" \
  --push \
  "${AGENT_DIR}"

echo ""
echo "Successfully pushed: ${IMAGE_URI}"
echo ""
echo "Next steps:"
echo "  terraform -chdir=infra init   # first time only"
echo "  terraform -chdir=infra apply -var=\"container_tag=${TAG}\""
echo ""
