#!/usr/bin/env bash
# Create the app namespace and its Secret (DB password + Flask secret key).
# Secrets are generated here and NEVER committed to Git. Argo CD manages everything
# else in k8s/, and the Deployments reference this Secret by name.
# shellcheck source=infra/common.sh
source "$(dirname "$0")/common.sh"

log "Namespace ${APP_NAMESPACE}"
kubectl create namespace "$APP_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

if kubectl -n "$APP_NAMESPACE" get secret student-portal-secrets >/dev/null 2>&1; then
  ok "Secret student-portal-secrets already exists - leaving it unchanged"
else
  kubectl -n "$APP_NAMESPACE" create secret generic student-portal-secrets \
    --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 24)" \
    --from-literal=FLASK_SECRET_KEY="$(openssl rand -hex 32)"
  ok "Secret student-portal-secrets created with random values"
fi
