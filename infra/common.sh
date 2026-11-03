#!/usr/bin/env bash
# Shared helpers: load config, derive account ID, pretty logging.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${INFRA_DIR}/.." && pwd)"
export INFRA_DIR REPO_ROOT

if [[ ! -f "${INFRA_DIR}/config.env" ]]; then
  echo "ERROR: ${INFRA_DIR}/config.env not found. Run: cp infra/config.env.example infra/config.env" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${INFRA_DIR}/config.env"
set +a

if [[ "${GITHUB_OWNER}" == "<"* ]]; then
  echo "ERROR: set GITHUB_OWNER in infra/config.env" >&2
  exit 1
fi

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

aws_account_id() { aws sts get-caller-identity --query Account --output text; }
