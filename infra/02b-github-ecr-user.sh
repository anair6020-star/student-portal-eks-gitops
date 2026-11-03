#!/usr/bin/env bash
# FALLBACK for AWS accounts where IAM OIDC providers are blocked (e.g. AWS Free plan,
# whose service control policy denies iam:*OpenIDConnectProvider).
# Creates an IAM user that can ONLY push to one ECR repository, and one access key
# for GitHub Actions. Prefer infra/02-github-oidc-role.sh wherever OIDC is allowed.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

USER_NAME="${GITHUB_ECR_USER:-github-actions-student-portal-ecr}"
ACCOUNT_ID=$(aws_account_id)
ECR_ARN="arn:aws:ecr:${AWS_REGION}:${ACCOUNT_ID}:repository/${ECR_REPOSITORY}"
export ECR_ARN
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

log "IAM user ${USER_NAME}"
if aws iam get-user --user-name "$USER_NAME" >/dev/null 2>&1; then
  ok "User already exists"
else
  aws iam create-user --user-name "$USER_NAME" \
    --tags Key=purpose,Value=github-actions-ecr-push Key=repo,Value="${GITHUB_OWNER}/${GITHUB_REPO}" >/dev/null
  ok "User created (no console password, programmatic access only)"
fi

envsubst < "${INFRA_DIR}/iam/github-ecr-push-policy.json" > "$TMP/policy.json"
aws iam put-user-policy --user-name "$USER_NAME" --policy-name ecr-push --policy-document file://"$TMP/policy.json"
ok "Least-privilege policy attached: push to ${ECR_REPOSITORY} only"

KEYS=$(aws iam list-access-keys --user-name "$USER_NAME" --query 'length(AccessKeyMetadata)' --output text)
if [[ "$KEYS" -ge 1 ]]; then
  warn "User already has an access key. Not creating another."
  warn "To rotate: delete the old key in IAM, then re-run this script."
  exit 0
fi

read -r AK SK < <(aws iam create-access-key --user-name "$USER_NAME" \
  --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text)

cat <<MSG

Add these in GitHub: repo > Settings > Secrets and variables > Actions.

SECRETS tab (encrypted). The secret key is shown ONLY ONCE. Copy it now,
never commit it, never paste it in chat:
  AWS_ACCESS_KEY_ID      = ${AK}
  AWS_SECRET_ACCESS_KEY  = ${SK}

VARIABLES tab (not secret):
  AWS_REGION      = ${AWS_REGION}
  ECR_REPOSITORY  = ${ECR_REPOSITORY}
  (Do NOT create AWS_ROLE_ARN. Leaving it unset selects this key-based mode.)

Then clear the terminal so the key is not left on screen:  clear
MSG
