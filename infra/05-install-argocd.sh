#!/usr/bin/env bash
# Install Argo CD (pinned version) and register the student-portal Application.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

# Argo CD must not sync before the pipeline has pushed the first image and written
# its ECR URI into k8s/kustomization.yaml. Run `git pull` first so this check is current.
if grep -q '<AWS_ACCOUNT_ID>' "${REPO_ROOT}/k8s/kustomization.yaml"; then
  warn "k8s/kustomization.yaml still has the placeholder image."
  warn "Run the GitHub Actions pipeline once (Step 5), then 'git pull', then re-run this script."
  exit 1
fi

log "Installing Argo CD ${ARGOCD_VERSION}"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
# --server-side is required for Argo CD v3 CRDs (they exceed the client-side annotation size limit).
kubectl apply -n argocd --server-side --force-conflicts \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

log "Waiting for Argo CD to become ready"
kubectl -n argocd rollout status deployment/argocd-server --timeout=300s
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=300s
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=300s
ok "Argo CD is running"

log "Registering Argo CD Application (repo ${GITHUB_OWNER}/${GITHUB_REPO}, path k8s/)"
sed -e "s#<GITHUB_OWNER>#${GITHUB_OWNER}#; s#<GITHUB_REPO>#${GITHUB_REPO}#" \
  "${REPO_ROOT}/argocd/application.yaml" | kubectl apply -f -
ok "Application created - Argo CD will sync automatically"

cat <<MSG

Argo CD UI (run on the EC2 box, keep it open):
  kubectl -n argocd port-forward svc/argocd-server 8443:443
  # From your laptop: ssh -i <key.pem> -L 8443:localhost:8443 ubuntu@<EC2_PUBLIC_IP>
  # Then open https://localhost:8443   (user: admin)

Initial admin password:
  argocd admin initial-password -n argocd

Status from the CLI:
  kubectl -n argocd get application student-portal
MSG
