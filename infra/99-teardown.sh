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
eksctl delete cluster --region "$AWS_REGION" --name "$CLUSTER_NAME" --wait || warn "Cluster delete reported an error - check CloudFormation"

log "Deleting ECR repository and images"
aws ecr delete-repository --region "$AWS_REGION" --repository-name "$ECR_REPOSITORY" --force >/dev/null || true

log "Deleting GitHub OIDC role"
aws iam delete-role-policy --role-name "$GITHUB_ROLE_NAME" --policy-name ecr-push || true
aws iam delete-role --role-name "$GITHUB_ROLE_NAME" || true
warn "The GitHub OIDC identity provider was kept (other repos may use it). Remove it in IAM if not needed."
ok "Teardown complete. Remember to stop/terminate the EC2 admin instance too."
