#!/usr/bin/env bash
# Let GitHub Actions push to ECR using OpenID Connect - no long-lived AWS keys in GitHub.
#  1. Registers GitHub's OIDC identity provider in IAM (once per AWS account).
#  2. Creates an IAM role that ONLY workflows on <owner>/<repo> branch main can assume.
#  3. Grants that role push access to ONE ECR repository, nothing else.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

ACCOUNT_ID=$(aws_account_id)
OIDC_HOST="token.actions.githubusercontent.com"
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_HOST}"
ECR_ARN="arn:aws:ecr:${AWS_REGION}:${ACCOUNT_ID}:repository/${ECR_REPOSITORY}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

log "GitHub OIDC identity provider"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  ok "Already registered"
else
  # AWS validates GitHub's certificate via its trusted CA library; the thumbprint is
  # required by the API but not used for GitHub. This is GitHub's published value.
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_HOST}" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
  ok "Registered"
fi

log "IAM role ${GITHUB_ROLE_NAME}"
export ACCOUNT_ID OIDC_ARN ECR_ARN
envsubst < "${INFRA_DIR}/iam/github-oidc-trust-policy.json" > "$TMP/trust.json"
envsubst < "${INFRA_DIR}/iam/github-ecr-push-policy.json"   > "$TMP/policy.json"

if aws iam get-role --role-name "$GITHUB_ROLE_NAME" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-document file://"$TMP/trust.json"
  ok "Role exists - trust policy refreshed"
else
  aws iam create-role --role-name "$GITHUB_ROLE_NAME" \
    --description "GitHub Actions (${GITHUB_OWNER}/${GITHUB_REPO}) push to ECR via OIDC" \
    --assume-role-policy-document file://"$TMP/trust.json" \
    --max-session-duration 3600 >/dev/null
  ok "Role created"
fi
aws iam put-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-name ecr-push \
  --policy-document file://"$TMP/policy.json"
ok "Least-privilege ECR push policy attached"

ROLE_ARN=$(aws iam get-role --role-name "$GITHUB_ROLE_NAME" --query Role.Arn --output text)
cat <<MSG

Add these as GitHub repository VARIABLES (Settings > Secrets and variables > Actions > Variables).
They are identifiers, not secrets:

  AWS_ROLE_ARN    = ${ROLE_ARN}
  AWS_REGION      = ${AWS_REGION}
  ECR_REPOSITORY  = ${ECR_REPOSITORY}

Or with the GitHub CLI:
  gh variable set AWS_ROLE_ARN   --repo ${GITHUB_OWNER}/${GITHUB_REPO} --body "${ROLE_ARN}"
  gh variable set AWS_REGION     --repo ${GITHUB_OWNER}/${GITHUB_REPO} --body "${AWS_REGION}"
  gh variable set ECR_REPOSITORY --repo ${GITHUB_OWNER}/${GITHUB_REPO} --body "${ECR_REPOSITORY}"
MSG
