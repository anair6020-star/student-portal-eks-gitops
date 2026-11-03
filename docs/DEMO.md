# End-to-end demonstration

```
Developer → GitHub → GitHub Actions → Docker image → Amazon ECR → Git deployment config → Argo CD → Amazon EKS → Running app
```

Before you start, open four windows:
1. **Browser tab: the app** (`http://<load-balancer-dns>`). Note the sidebar **Live deployment** badge and the footer: `Version <sha>` and `Served by pod ...`. The dashboard's **Release pipeline** card shows the same build and pod.
2. **Browser tab: GitHub → Actions.**
3. **Browser tab: Argo CD UI** (`https://localhost:8443` through the SSH tunnel).
4. **Terminal on EC2** with a watch running:
   ```bash
   kubectl -n student-portal get pods -w
   ```

Record the starting state:
```bash
kubectl -n argocd get application student-portal
kubectl -n student-portal get deploy student-portal -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

## Demo A: application change (full pipeline)

1. Change the dashboard heading in `app/templates/dashboard.html`:
   ```html
   <h1 id="hero-title" class="hero-title">Welcome to the Student Portal</h1>
   ```
   to
   ```html
   <h1 id="hero-title" class="hero-title">Welcome to the Student Portal - Batch 2026</h1>
   ```
   (Keep the words "Welcome to the Student Portal": the unit test and the CI smoke test check for them. If you change those words, update `tests/test_app.py` and the smoke test too, which is a good way to show the tests guarding the release.)

2. Commit and push:
   ```bash
   git add app/templates/dashboard.html
   git commit -m "feat: show batch year in heading"
   git push origin main
   ```

3. Show each stage:

   | Stage | Where to look | What you should see |
   |---|---|---|
   | GitHub Actions | Actions tab → newest run | `test` ✓ → `build-and-push` ✓ → `update-manifest` ✓ |
   | Docker image + ECR | Run summary, or `aws ecr describe-images --repository-name student-portal --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageTags'` | New tag = first 7 characters of your commit SHA |
   | Git deployment config | Repo commits | Bot commit `deploy: student-portal <sha>` changing `k8s/kustomization.yaml` |
   | Argo CD | UI, or `argocd app get student-portal --refresh` | Detects the new revision, syncs, returns to **Synced / Healthy** |
   | EKS | Terminal watch | New pods start and become Ready, then old pods terminate (zero downtime) |
   | Running app | Refresh the browser | New heading; footer shows the new version SHA |

   ```bash
   kubectl -n student-portal rollout status deploy/student-portal
   kubectl -n student-portal get deploy student-portal -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
   curl -s http://<load-balancer-dns>/version
   ```

## Demo B: deployment-config-only change (pure GitOps)

Shows that a change to the deployment configuration in Git, with no code change, is applied to EKS by Argo CD.

```bash
# Scale from 2 to 3 replicas in Git
sed -i 's/^  replicas: 2$/  replicas: 3/' k8s/deployment.yaml
git commit -am "ops: scale student-portal to 3 replicas"
git push origin main
```
- GitHub Actions does **not** run (`k8s/**` is in `paths-ignore`): no new image is needed.
- Argo CD syncs within ~3 minutes (or click **Refresh**), and a third pod appears.
  ```bash
  kubectl -n student-portal get pods -l app.kubernetes.io/name=student-portal
  ```

## Demo C: self-heal (drift correction)

```bash
kubectl -n student-portal scale deploy student-portal --replicas=6
kubectl -n student-portal get pods -w
```
Argo CD sees the cluster no longer matches Git and scales back to the value in Git within seconds.

## Demo D: rollback with Git

```bash
git log --oneline -5                     # find the bot's "deploy: student-portal <sha>" commit
git revert --no-edit <deploy-commit-sha>
git push origin main
```
Argo CD rolls the Deployment back to the previous image. The footer shows the old version again.

---

## Evidence checklist (screenshots for submission)

| # | Screenshot | Shows |
|---|---|---|
| 1 | GitHub repo home with README | Task 1 |
| 2 | EC2 terminal: `docker --version`, `aws --version`, `kubectl version --client`, `aws sts get-caller-identity` (assumed role, no keys) | Task 2 |
| 3 | `docker build` output and local `curl /healthz` | Task 3 |
| 4 | ECR console: repository with image tags, scan results, immutable tags | Task 3 |
| 5 | `kubectl get nodes` and `kubectl -n student-portal get pods,svc` | Task 4 |
| 6 | App in browser via the load balancer URL | Task 4 |
| 7 | IAM role trust policy showing the GitHub OIDC provider and `repo:...:ref:refs/heads/main` | Task 5 |
| 8 | GitHub Actions run with all three jobs green | Task 5 |
| 9 | Bot commit updating `k8s/kustomization.yaml` | Task 5 |
| 10 | Argo CD UI: application tree, **Synced** and **Healthy** | Task 6 |
| 11 | Argo CD sync after the replicas change (Demo B) | Task 6 |
| 12 | Before/after browser screenshots: heading and footer version changed (Demo A) | Task 7 |
