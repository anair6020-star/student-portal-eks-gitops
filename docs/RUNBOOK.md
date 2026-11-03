# Runbook: step-by-step setup

Each section maps to a task in the assignment. Commands are meant to be copied as-is; replace values in `<angle brackets>`.

**Assumed defaults** (change in `infra/config.env`): region `ap-south-1` (Mumbai), cluster `student-portal-eks`, ECR repo `student-portal`, branch `main`.

| # | Task | Where you run it | Time |
|---|---|---|---|
| 1 | GitHub repo | Laptop / browser | 5 min |
| 2 | EC2 admin box + IAM | AWS Console, then SSH | 15 min |
| 3 | Docker image + ECR | EC2 | 10 min |
| 4 | EKS cluster + kubectl | EC2 | 20 min (cluster create) |
| 5 | GitHub Actions + OIDC | EC2 + GitHub | 10 min |
| 6 | Argo CD | EC2 | 10 min |
| 7 | End-to-end demo | See [DEMO.md](DEMO.md) | 15 min |

---

## 1. Application and GitHub

The application, tests and README are already in this repository. If you are starting from your own GitHub account:

1. Create an empty **public** repository named `student-portal-eks-gitops` (public lets Argo CD read it without credentials; see the note at the end for private repos).
2. Push this code:
   ```bash
   git remote add origin https://github.com/<GITHUB_OWNER>/student-portal-eks-gitops.git
   git push -u origin main
   ```
3. GitHub → **Settings → Actions → General → Workflow permissions**: choose **Read and write permissions** (the pipeline commits the new image tag back to `main`).
   If `main` has branch protection that blocks direct pushes, allow `github-actions[bot]` to bypass it, or the `update-manifest` job will fail.

## 2. AWS EC2 environment

### 2.1 IAM role for the EC2 instance (no access keys on the box)

Console: **IAM → Roles → Create role → AWS service → EC2** → attach a policy → name it `sis-admin-ec2-role`.

Policy choice:
- **Lab account (simplest):** `AdministratorAccess`. `eksctl` needs to create IAM roles, CloudFormation stacks, a VPC and the cluster. Detach it after the assignment.
- **Least privilege:** use the eksctl minimum IAM policies (<https://eksctl.io/usage/minimum-iam-policies/>) plus ECR and IAM permissions for scripts 01 and 02.

Equivalent AWS CLI (e.g. from CloudShell):
```bash
aws iam create-role --role-name sis-admin-ec2-role \
  --assume-role-policy-document file://infra/iam/ec2-admin-trust-policy.json
aws iam attach-role-policy --role-name sis-admin-ec2-role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam create-instance-profile --instance-profile-name sis-admin-ec2-profile
aws iam add-role-to-instance-profile --instance-profile-name sis-admin-ec2-profile \
  --role-name sis-admin-ec2-role
```

### 2.2 Launch the instance

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS |
| Type | `t3.medium` (Docker builds need ~2 GB RAM) |
| Storage | 20 GB gp3 |
| Security group | Inbound **SSH 22 from My IP only**. Nothing else. |
| IAM instance profile | `sis-admin-ec2-role` |
| Metadata | IMDSv2 required (default on new launches) |

### 2.3 Install the tools

```bash
ssh -i <key.pem> ubuntu@<EC2_PUBLIC_IP>
git clone https://github.com/<GITHUB_OWNER>/student-portal-eks-gitops.git
cd student-portal-eks-gitops
bash infra/00-ec2-bootstrap.sh
newgrp docker            # or log out and back in

# Verify
docker run --rm hello-world
aws sts get-caller-identity      # Arn must show assumed-role/sis-admin-ec2-role/...
kubectl version --client
eksctl version
```

Do **not** run `aws configure` with access keys. The instance role supplies temporary credentials automatically.

### 2.4 Project config

```bash
cp infra/config.env.example infra/config.env
nano infra/config.env     # set GITHUB_OWNER (and region/cluster name if different)
```

## 3. Docker and Amazon ECR

```bash
# Build and test the image locally on EC2
docker build --build-arg APP_VERSION=local -t student-portal:local .
docker run -d --name sis -p 8080:8080 student-portal:local
curl -s localhost:8080/healthz        # {"status":"ok","version":"local"}
curl -s localhost:8080/ | grep "Welcome to the Student Portal"
docker rm -f sis

# Create the ECR repository (immutable tags, scan on push, lifecycle policy)
bash infra/01-create-ecr.sh
```

Manual first push (shows Docker-to-ECR authentication; the pipeline does this automatically afterwards):
```bash
source infra/config.env
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY
docker tag student-portal:local $REGISTRY/$ECR_REPOSITORY:manual-1
docker push $REGISTRY/$ECR_REPOSITORY:manual-1
aws ecr describe-images --repository-name $ECR_REPOSITORY --region $AWS_REGION \
  --query 'imageDetails[].imageTags' --output table
```

## 4. Amazon EKS

**New cluster** (about 15-20 minutes):
```bash
bash infra/03-create-eks-cluster.sh
```

**Cluster provided by the instructor:**
```bash
# 1) The cluster owner grants your EC2 role access (run by them, once):
aws eks create-access-entry --cluster-name <CLUSTER> --region <REGION> \
  --principal-arn arn:aws:iam::<ACCOUNT_ID>:role/sis-admin-ec2-role
aws eks associate-access-policy --cluster-name <CLUSTER> --region <REGION> \
  --principal-arn arn:aws:iam::<ACCOUNT_ID>:role/sis-admin-ec2-role \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
# 2) You: set CLUSTER_NAME/AWS_REGION in infra/config.env, then
bash infra/03-create-eks-cluster.sh --existing
```

Check:
```bash
kubectl get nodes          # 2 nodes, STATUS Ready
```

Create the namespace and the application Secret (random DB password and Flask key, not stored in Git):
```bash
bash infra/04-bootstrap-app-secrets.sh
```

> The Deployment and Service YAML manifests are in `k8s/`. They are deployed by Argo CD in step 6, which is the GitOps way. To see them deployed directly first (optional, after step 5 has pushed an image), run `kubectl apply -k k8s/` and then let Argo CD adopt them.

## 5. CI/CD with GitHub Actions (OIDC)

```bash
bash infra/02-github-oidc-role.sh
```
This registers GitHub's OIDC provider in IAM and creates role `github-actions-student-portal-ecr`, which:
- can be assumed **only** by `repo:<GITHUB_OWNER>/student-portal-eks-gitops:ref:refs/heads/main`
- can **only** push to the one ECR repository

Add the three values it prints as **repository variables**: GitHub → Settings → Secrets and variables → Actions → **Variables** tab → New repository variable:

| Name | Example |
|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::123456789012:role/github-actions-student-portal-ecr` |
| `AWS_REGION` | `ap-south-1` |
| `ECR_REPOSITORY` | `student-portal` |

Run the pipeline the first time: GitHub → **Actions → CI/CD → Run workflow** (on `main`).

Expected result:
1. `test` passes (lint + 66 tests).
2. `build-and-push` builds, smoke-tests and pushes `<registry>/student-portal:<sha>`.
3. `update-manifest` commits `deploy: student-portal <sha>` changing `k8s/kustomization.yaml`.

Pull that commit on EC2:
```bash
git pull
grep -A3 "images:" k8s/kustomization.yaml     # newName = your ECR URI, newTag = the SHA
```

## 6. GitOps with Argo CD

```bash
bash infra/05-install-argocd.sh
```
This installs Argo CD v3.5.7, waits until it is ready, and applies `argocd/application.yaml` with your repo URL. The Application has **automated sync, prune and self-heal** enabled.

Check status:
```bash
kubectl -n argocd get applications
# NAME             SYNC STATUS   HEALTH STATUS
# student-portal   Synced        Healthy

kubectl -n student-portal get pods
kubectl -n student-portal get svc student-portal
```
Health becomes `Healthy` once the load balancer has an address (2-3 minutes).

Open the app:
```bash
echo "http://$(kubectl -n student-portal get svc student-portal -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
```
(The DNS name can take a few minutes to resolve the first time.)

Open the Argo CD UI:
```bash
argocd admin initial-password -n argocd           # copy the password
kubectl -n argocd port-forward svc/argocd-server 8443:443
# On your laptop, in another terminal:
ssh -i <key.pem> -L 8443:localhost:8443 ubuntu@<EC2_PUBLIC_IP>
# Browse https://localhost:8443  →  user: admin  (accept the self-signed certificate)
```
Optional CLI login: `argocd login localhost:8443 --username admin --insecure`.

## 7. End-to-end demonstration

See **[DEMO.md](DEMO.md)**.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not assume role with OIDC` | Variable `AWS_ROLE_ARN` wrong, or repo/branch name differs from the trust policy | Check `GITHUB_OWNER`/`GITHUB_REPO` in `config.env`, re-run `02-github-oidc-role.sh` |
| `update-manifest` fails with 403 | Workflow permissions are read-only, or branch protection | Step 1.3 |
| Pods `ImagePullBackOff` | Image tag not in ECR, or region mismatch | `aws ecr describe-images ...`; confirm `newName` region matches cluster region |
| Pods `CreateContainerConfigError` | Secret missing | `bash infra/04-bootstrap-app-secrets.sh` |
| Web pods `Running` but `0/1 Ready` | Database not ready yet | `kubectl -n student-portal logs deploy/student-portal-db`; it recovers automatically |
| Argo CD `OutOfSync` / `Unknown` | Repo URL wrong, or repo is private | `kubectl -n argocd describe application student-portal` |
| Service `EXTERNAL-IP <pending>` for > 5 min | Subnets missing ELB tags (only with custom VPCs) | `kubectl -n student-portal describe svc student-portal` events |
| Argo CD slow to notice a commit | Default polling interval is ~3 minutes | Click **Refresh** in the UI or `argocd app get student-portal --refresh` |

**Private repository:** give Argo CD read access with a fine-grained GitHub token (Contents: Read-only, this repo only):
```bash
argocd repo add https://github.com/<GITHUB_OWNER>/student-portal-eks-gitops.git \
  --username <GITHUB_OWNER> --password <FINE_GRAINED_TOKEN>
```
Never commit that token.
