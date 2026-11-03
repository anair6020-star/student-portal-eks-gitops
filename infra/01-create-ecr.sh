#!/usr/bin/env bash
# Create the Amazon ECR repository (idempotent).
#  - Tag immutability: a tag (git SHA) can never be overwritten -> deployments are traceable.
#  - Scan on push: basic vulnerability scan for every image.
#  - Lifecycle policy: keep the 20 most recent images to control storage cost.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

log "Creating ECR repository ${ECR_REPOSITORY} in ${AWS_REGION}"
if aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPOSITORY" >/dev/null 2>&1; then
  ok "Repository already exists"
else
  aws ecr create-repository --region "$AWS_REGION" \
    --repository-name "$ECR_REPOSITORY" \
    --image-tag-mutability IMMUTABLE \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 >/dev/null
  ok "Repository created"
fi

aws ecr put-lifecycle-policy --region "$AWS_REGION" --repository-name "$ECR_REPOSITORY" \
  --lifecycle-policy-text file://"${INFRA_DIR}/iam/ecr-lifecycle-policy.json" >/dev/null
ok "Lifecycle policy applied"

URI=$(aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPOSITORY" \
  --query 'repositories[0].repositoryUri' --output text)
echo
echo "ECR repository URI: ${URI}"
