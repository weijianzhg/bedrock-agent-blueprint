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
#   - Terraform applied (infra/)
# -------------------------------------------------------------------

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/agents"
INFRA_DIR="${ROOT_DIR}/infra"

# Read ECR repository URL from Terraform output
echo "Reading ECR repository URL from infra/..."
ECR_URL=$(terraform -chdir="$INFRA_DIR" output -raw ecr_repository_url)
AWS_REGION=$(aws configure get region 2>/dev/null || echo "eu-west-1")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
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
echo "  terraform -chdir=infra apply -var=\"container_tag=${TAG}\""
echo ""
