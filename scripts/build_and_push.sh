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
#   - Terraform outputs available (run `terraform apply` in infra/ first)
# -------------------------------------------------------------------

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/agents"
INFRA_DIR="${ROOT_DIR}/infra"

# Read ECR repository URL from Terraform output
echo "Reading ECR repository URL from Terraform..."
ECR_URL=$(cd "$INFRA_DIR" && terraform output -raw ecr_repository_url)
AWS_REGION=$(cd "$INFRA_DIR" && terraform output -raw 2>/dev/null || echo "us-east-1")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TAG="${IMAGE_TAG:-latest}"

IMAGE_URI="${ECR_URL}:${TAG}"

echo ""
echo "Agent directory : ${AGENT_DIR}"
echo "ECR image URI   : ${IMAGE_URI}"
echo ""

# Authenticate with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Build ARM64 image
echo "Building ARM64 image..."
docker buildx build \
  --platform linux/arm64 \
  -f "${AGENT_DIR}/Dockerfile" \
  -t "${IMAGE_URI}" \
  --push \
  "${AGENT_DIR}"

echo ""
echo "Successfully pushed: ${IMAGE_URI}"
echo ""
echo "Next steps:"
echo "  1. cd infra && terraform apply   (to update the runtime with the new image)"
echo "  2. python scripts/invoke.py      (to test the deployed agent)"
