# DevOps Coursework — Sessions 13 to 20

**Name:** Aman Yadav
**Roll Number:** 24bcs10183
**Year:** 2nd Year
**Batch:** A
**Run date:** 7 October 2026

Eight homework sets from the official course document, each executed end to end. Every output block
is captured terminal output, not an example from documentation.

---

## Sections

| # | Session | Write-up | Manifests | What it proves |
|---|---|---|---|---|
| 13 | [Storage, HPA & Probes](13-storage-hpa-probes/README.md) | 3,217 lines | 37 | HPA scaling 1→4 under measured load, the 300s scale-down window timed, and access modes tested rather than assumed |
| 14 | [Kubernetes Troubleshooting](14-k8s-troubleshooting/README.md) | 2,693 lines | 33 | Twelve failure modes reproduced with their real error text, each diagnosed and fixed |
| 15 | [Helm](15-helm/README.md) | 3,836 lines | 22 | Install → upgrade → rollback across seven revisions, verified against running pods |
| 16 | [CI/CD & GitHub Actions](16-github-actions/README.md) | 1,258 lines | 1 | A six-job pipeline genuinely green on GitHub, with the two real failures that preceded it |
| 17 | [DevSecOps](17-devsecops/README.md) | — | — | SAST, SCA, secret and image scanning, and a security gate that actually blocks a build |
| 18 | [Terraform & IaC](18-terraform-iac/README.md) | 4,261 lines | 4 | Full terraform lifecycle plus five AWS service write-ups grounded in real API calls |
| 19 | [Cloud & Terraform in Action](19-cloud-terraform/README.md) | 2,310 lines | 4 | VPC → Subnet → SG → EC2 → S3 with dependency ordering proved by `terraform graph` |
| 20 | [Monitoring, Observability & GitOps](20-monitoring-gitops/README.md) | 2,222 lines | 13 | An alert driven from inactive to firing, and a full GitOps drift-and-heal cycle |

---

## Environment

| Component | Version |
|---|---|
| Cluster | minikube v1.39.0, docker driver, 6 CPU / 7000 MB |
| Kubernetes | v1.37.0, containerd 2.3.4 |
| Addons | storage-provisioner, default-storageclass, ingress, metrics-server |
| Helm | v4.3.0 |
| Terraform | v1.16.4 |
| Scanners | trivy 0.75.0, gitleaks 8.30.1 |
| Host | macOS arm64, Docker Desktop (7935 MB ceiling) |

Rebuild the cluster these labs ran on:

```bash
minikube start --driver=docker --cpus=6 --memory=7000
minikube addons enable ingress
minikube addons enable metrics-server
```

---

## Two things to know before re-running these

**The node IP is unreachable from macOS.** With the docker driver the node lives inside the Docker
Desktop VM, so `ping 192.168.49.2` gives 100% packet loss and curl times out. Use
`minikube ssh -- curl ...`, `minikube service <svc> -n <ns> --url`, `kubectl port-forward`, or curl
from an in-cluster pod. Every session documents which method it used.

**AWS ran against LocalStack, not real AWS.** Sessions 18 and 19 had no AWS credentials, so the
terraform lifecycle ran against `localstack/localstack:3.8` (community edition) on port 4566. The
terraform workflow is real; the cloud behind it is emulated. Both READMEs say so at the top and list
what differs. Note that `localstack/localstack:latest` is now a paid build that exits with code 55.

---

## Limits found and documented, not hidden

These are the places where the tooling did not behave the way the material assumes. Each is recorded
in its session with the real output rather than smoothed over.

| Finding | Session |
|---|---|
| `ReadOnlyMany` is not enforced — a write into a ROX volume succeeded | 13 |
| `volumeBindingMode: WaitForFirstConsumer` is unusable on stock minikube (provisioner RBAC cannot get nodes) | 13 |
| HPA never reached `maxReplicas` because the node, not the pod, was the bottleneck | 13 |
| A memory-backed `emptyDir` produces `RunContainerError`, not a true `OOMKilled` | 14 |
| Helm 4 removed `helm list --all` and deprecated bare `--dry-run` | 15 |
| A SemVer `+build` suffix is not a legal Docker tag | 16 |
| LocalStack stores bucket policies but does not enforce them | 18 |
| RDS is absent from LocalStack community entirely | 18 |
| LocalStack `DescribeInstances` omits security groups, causing a perpetual terraform diff | 19 |
| LocalStack's EC2 reports `running` with no VM behind it | 19 |

---

## Conventions

Each session worked in its own namespace (`hw13` … `hw20`) with its own NodePort range, so all eight
could run concurrently against one cluster without collisions. Every namespace was deleted afterwards
and the teardown verified. AWS resources were prefixed `hw18-` / `hw19-` and destroyed.

Configuration files carry no explanatory comments by request; the prose lives in the READMEs.
