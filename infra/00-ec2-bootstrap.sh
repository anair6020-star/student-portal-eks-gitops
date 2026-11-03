#!/usr/bin/env bash
# Run ONCE on a fresh Ubuntu 24.04 EC2 instance (the admin/dev box).
# Installs: Docker Engine, AWS CLI v2, kubectl, eksctl, Argo CD CLI, git, jq, yq, envsubst.
#   bash infra/00-ec2-bootstrap.sh
set -euo pipefail

K8S_MINOR="${K8S_MINOR:-1.35}"         # kubectl must be within +/-1 minor of the cluster
EKSCTL_VERSION="${EKSCTL_VERSION:-v0.231.0}"
ARGOCD_VERSION="${ARGOCD_VERSION:-v3.5.7}"
YQ_VERSION="${YQ_VERSION:-v4.54.1}"

case "$(uname -m)" in
  x86_64)  ARCH=amd64 ;;
  aarch64) ARCH=arm64 ;;
  *) echo "Unsupported architecture $(uname -m)"; exit 1 ;;
esac

echo "==> Base packages"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg unzip git jq gettext-base python3 python3-venv

echo "==> Docker Engine (official Docker apt repository)"
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
fi

echo "==> AWS CLI v2"
if ! command -v aws >/dev/null; then
  AWS_ARCH=$([[ $ARCH == amd64 ]] && echo x86_64 || echo aarch64)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_ARCH}.zip" -o /tmp/awscliv2.zip
  unzip -q -o /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install --update && rm -rf /tmp/aws /tmp/awscliv2.zip
fi

echo "==> kubectl (${K8S_MINOR}.x)"
KUBECTL_VERSION="$(curl -fsSL "https://dl.k8s.io/release/stable-${K8S_MINOR}.txt")"
curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl"
curl -fsSLo /tmp/kubectl.sha256 "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl.sha256"
echo "$(cat /tmp/kubectl.sha256)  /tmp/kubectl" | sha256sum --check
sudo install -m 0755 /tmp/kubectl /usr/local/bin/kubectl && rm -f /tmp/kubectl /tmp/kubectl.sha256

echo "==> eksctl ${EKSCTL_VERSION}"
curl -fsSL "https://github.com/eksctl-io/eksctl/releases/download/${EKSCTL_VERSION}/eksctl_Linux_${ARCH}.tar.gz" \
  | sudo tar -xz -C /usr/local/bin eksctl

echo "==> Argo CD CLI ${ARGOCD_VERSION}"
sudo curl -fsSLo /usr/local/bin/argocd \
  "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-${ARCH}"
sudo chmod 0755 /usr/local/bin/argocd

echo "==> yq ${YQ_VERSION}"
sudo curl -fsSLo /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_${ARCH}"
sudo chmod 0755 /usr/local/bin/yq

echo
echo "==> Installed versions"
docker --version
aws --version
kubectl version --client
eksctl version
argocd version --client --short 2>/dev/null || argocd version --client
yq --version
echo
echo "Done. Log out and back in (or run 'newgrp docker') so Docker works without sudo."
echo "Then verify AWS identity (should be the EC2 instance role, NOT access keys):"
echo "  aws sts get-caller-identity"
