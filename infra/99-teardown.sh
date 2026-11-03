#!/usr/bin/env bash
# Delete everything this project created, to stop AWS charges.
# Order matters: delete the LoadBalancer Service first so AWS removes the ELB
# before eksctl tries to delete the VPC.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

read -r -p "Delete cluster ${CLUSTER_NAME}, ECR repo ${ECR_REPOSITORY} and role ${GITHUB_ROLE_NAME}? [y/N] " ans
[[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted"; exit 1; }

log "Removing Argo CD Application (prunes app resources incl. the load balancer)"
kubectl -n argocd delete application student-portal --ignore-not-found --wait=true || true
kubectl -n "$APP_NAMESPACE" delete service student-portal --ignore-not-found --wait=true || true
sleep 30

log "Deleting EKS cluster (~10-15 min)"
# eksctl delete checks for an IAM OIDC provider first. On AWS Free plan accounts that
# call is denied by a service control policy, so fall back to deleting eksctl's
# CloudFormation stacks directly (nodegroups first, then the cluster stack).
if ! eksctl delete cluster --region "$AWS_REGION" --name "$CLUSTER_NAME" --wait; then
  warn "eksctl delete failed - deleting CloudFormation stacks directly"
  delete_stack() {
    # eksctl turns on termination protection for its stacks; turn it off first.
    aws cloudformation update-termination-protection --region "$AWS_REGION" \
      --no-enable-termination-protection --stack-name "$1" >/dev/null || true
    aws cloudformation delete-stack --region "$AWS_REGION" --stack-name "$1"
    if aws cloudformation wait stack-delete-complete --region "$AWS_REGION" --stack-name "$1"; then
      ok "Deleted stack $1"
    else
      warn "Stack $1 did not delete cleanly - check the CloudFormation console"
    fi
  }
  for s in $(aws cloudformation list-stacks --region "$AWS_REGION" \
      --stack-status-filter CREATE_COMPLETE CREATE_FAILED ROLLBACK_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE DELETE_FAILED \
      --query "StackSummaries[?starts_with(StackName, 'eksctl-${CLUSTER_NAME}-nodegroup-')].StackName" --output text); do
    delete_stack "$s"
  done
  delete_stack "eksctl-${CLUSTER_NAME}-cluster"
fi

log "Deleting ECR repository and images"
aws ecr delete-repository --region "$AWS_REGION" --repository-name "$ECR_REPOSITORY" --force >/dev/null || true

log "Deleting GitHub OIDC role"
aws iam delete-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-name ecr-push || true
aws iam delete-role --role-name "$GITHUB_ROLE_NAME" || true
warn "The GitHub OIDC identity provider was kept (other repos may use it). Remove it in IAM if not needed."
ok "Teardown complete. Remember to stop/terminate the EC2 admin instance too."
