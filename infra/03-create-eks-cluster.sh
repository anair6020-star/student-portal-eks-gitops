#!/usr/bin/env bash
# Create the EKS cluster with eksctl (~15-20 min) OR connect to an existing one.
#   bash infra/03-create-eks-cluster.sh            # create new cluster
#   bash infra/03-create-eks-cluster.sh --existing # cluster was provided: just configure kubectl
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

if [[ "${1:-}" == "--existing" ]]; then
  log "Connecting kubectl to existing cluster ${CLUSTER_NAME}"
else
  if aws eks describe-cluster --region "$AWS_REGION" --name "$CLUSTER_NAME" >/dev/null 2>&1; then
    ok "Cluster ${CLUSTER_NAME} already exists - skipping create"
  else
    log "Creating EKS cluster ${CLUSTER_NAME} (Kubernetes ${K8S_VERSION}) in ${AWS_REGION} - takes ~15-20 min"
    envsubst < "${INFRA_DIR}/eks-cluster.yaml" > /tmp/eks-cluster.rendered.yaml
    eksctl create cluster -f /tmp/eks-cluster.rendered.yaml
  fi
fi

aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"
log "Cluster check"
kubectl cluster-info
kubectl get nodes -o wide
ok "kubectl is talking to ${CLUSTER_NAME}"
