#!/usr/bin/env bash
# Build the agent Docker image (ARM64) and push it to ECR.
#
# Usage:
#   AWS_PROFILE=my-profile ./scripts/build_and_push.sh
#   IMAGE_TAG=v1 ./scripts/build_and_push.sh
#
# Prerequisites:
#   - Docker running, with buildx
#   - Terraform and AWS CLI with configured credentials
#
# Terraform creates/manages the ECR repository before the first image build.
# If using a remote backend, initialize infra/ with its backend settings first.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/agents"
INFRA_DIR="${ROOT_DIR}/infra"
# Fail before creating AWS resources if the local build tools are unavailable.
for BUILD_TOOL in aws terraform docker; do
  command -v "$BUILD_TOOL" >/dev/null || { echo "Required tool missing: $BUILD_TOOL" >&2; exit 1; }
done
docker buildx version >/dev/null
docker info >/dev/null
# Include build time so uncommitted edits still produce a new runtime version.
TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD)-$(date -u +%Y%m%d%H%M%S)}"

# AWS_PROFILE is inherited by both Terraform and the AWS CLI. Explicit .tfvars
# settings take precedence over this fallback region, as Terraform normally does.
DEPLOY_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [ -z "$DEPLOY_REGION" ]; then
  DEPLOY_REGION="$(aws configure get region || true)"
fi
export TF_VAR_aws_region="${TF_VAR_aws_region:-${DEPLOY_REGION:-eu-west-1}}"

terraform -chdir="$INFRA_DIR" init -input=false
# Only the repository is needed before an image exists. Auto-approve is scoped
# to these two resources; the full infrastructure apply remains a separate step.
terraform -chdir="$INFRA_DIR" apply -input=false -auto-approve \
  -target=aws_ecr_repository.agent \
  -target=aws_ecr_lifecycle_policy.agent
ECR_URL="$(terraform -chdir="$INFRA_DIR" output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_URL%%/*}"
if [[ ! "$ECR_REGISTRY" =~ ^[0-9]+\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com(\.cn)?$ ]]; then
  echo "Terraform returned an invalid ECR URL: $ECR_URL" >&2
  exit 1
fi
# Use the repository's actual region, including any override from .tfvars.
DEPLOY_REGION="${BASH_REMATCH[1]}"
IMAGE_URI="${ECR_URL}:${TAG}"

aws ecr get-login-password --region "$DEPLOY_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "Building and pushing ARM64 image: $IMAGE_URI"
docker buildx build \
  --platform linux/arm64 \
  --provenance=false \
  -f "${AGENT_DIR}/Dockerfile" \
  -t "${IMAGE_URI}" \
  -t "${ECR_URL}:latest" \
  --push \
  "${AGENT_DIR}"

echo "Successfully pushed: ${IMAGE_URI}"
echo "Deploy the runtime:"
echo "  terraform -chdir=\"$INFRA_DIR\" apply -var=\"aws_region=${DEPLOY_REGION}\" -var=\"container_tag=${TAG}\""
