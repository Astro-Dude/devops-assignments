# DevOps Assignments

Homework submissions for the DevOps course, covering Linux, shell scripting,
networking, Git, Docker, Kubernetes, Helm, CI/CD and DevSecOps, Terraform,
monitoring and GitOps, and a final end-to-end project.

All documentation in this repository contains **real captured command output**
from live systems — not sample or illustrative text. Linux exercises were run
in an Ubuntu 22.04 container with systemd enabled; Docker exercises were run on
a live Docker engine. Docker web applications have browser screenshots; the
Kubernetes and Helm submissions include captured CLI and HTTP checks. The CI/CD
submissions ran on GitHub Actions in this repository. The Terraform submissions
ran against a local AWS API emulator, because no AWS account was used.

## Contents

| Session | Topic | Submission |
|---|---|---|
| 2 | Linux Fundamentals | [DevOps/02-linux-fundamentals](DevOps/02-linux-fundamentals/README.md) |
| 3 | Shell Scripting | [DevOps/03-shell-scripting](DevOps/03-shell-scripting/README.md) |
| 4 | Networking Fundamentals | [DevOps/04-networking](DevOps/04-networking/README.md) |
| 5 | Git / GitHub | [DevOps/05-git-github](DevOps/05-git-github/README.md) |
| 6 | Docker Fundamentals | [DevOps/06-docker-fundamentals](DevOps/06-docker-fundamentals/README.md) |
| 7 | Dockerfiles & Images | [DevOps/07-dockerfiles-images](DevOps/07-dockerfiles-images/README.md) |
| 8 | Docker Networking | [DevOps/08-docker-network](DevOps/08-docker-network/README.md) |
| 9 | Kubernetes Fundamentals | [DevOps/09-kubernetes-fundamentals](DevOps/09-kubernetes-fundamentals/README.md) |
| 10 | Kubernetes Core Objects | [DevOps/10-k8s-core-objects](DevOps/10-k8s-core-objects/README.md) |
| 11 | Kubernetes Services | [DevOps/11-kubernetes-services](DevOps/11-kubernetes-services/README.md) |
| 12 | Ingress, ConfigMaps & Secrets | [DevOps/12-ingress-configmaps-secrets](DevOps/12-ingress-configmaps-secrets/README.md) |
| 13 | Storage, HPA & Probes | [DevOps/13-storage-hpa-probes](DevOps/13-storage-hpa-probes/README.md) |
| 14 | Kubernetes Troubleshooting | [DevOps/14-kubernetes-troubleshooting](DevOps/14-kubernetes-troubleshooting/README.md) |
| 15 | Helm | [DevOps/15-helm](DevOps/15-helm/README.md) |
| 16 | CI/CD & GitHub Actions | [DevOps/16-github-actions](DevOps/16-github-actions/README.md) |
| 17 | Complete CI/CD & DevSecOps | [DevOps/17-devsecops](DevOps/17-devsecops/README.md) |
| 18 | Terraform & Infrastructure as Code | [DevOps/18-terraform-iac](DevOps/18-terraform-iac/README.md) |
| 19 | Cloud & Terraform in Action | [DevOps/19-cloud-terraform](DevOps/19-cloud-terraform/README.md) |
| 20 | Monitoring, Observability & GitOps | [DevOps/20-monitoring-observability-gitops](DevOps/20-monitoring-observability-gitops/README.md) |
| 21 | Final DevOps Project & Troubleshooting | [DevOps/21-final-devops-project](DevOps/21-final-devops-project/README.md) |

Folder numbers match the course session numbers. Session 1 (DevOps engineer
roadmap) had no homework, so the first submission is `02`.
Source: [devops-heros](https://github.com/Nency-Ravaliya/devops-heros),
reviewed at commit `f25086a66daf1465336e4daeb0ce4cff1e0ac3c9`.

## What each one covers

**2. Linux Fundamentals** — soft vs hard links demonstrated through inode and
link-count evidence; `adduser` vs `useradd` compared by actually creating users
with both; `journalctl` practised against a real systemd journal, including
locating a genuine nginx config error by file and line; a ~90-command cheat
sheet with output.

**3. Shell Scripting** — a system information script using variables,
`read -p`, `mkdir`, `touch`, `df`, `ps` and `>` redirection, with transcripts of
both a custom-input run and a defaults run.

**4. Networking** — 10 sections covering interfaces, routing, ARP, `ping`,
`traceroute`/`mtr`, DNS, sockets, port testing, `curl`/`wget`, `tcpdump` and
`whois`, each with output and an explanation of what it means.

**5. Git / GitHub** — `git commit -m` vs `git commit -a -m` across five
scenarios including the untracked-file trap; a full cherry-pick exercise moving
one commit between branches.

**6. Docker Fundamentals** — six Hello World web apps (Node.js, Python, Java,
Apache, React, Nginx), each with its own Dockerfile, built, run, and verified
with browser screenshots.

**7. Dockerfiles & Images** — a multi-stage build serving *Hello World from
Docker multi-stage build* on port 8080, with a measured size comparison against
the single-stage equivalent.

**8. Docker Networking** — a three-tier topology across three networks with the
backend dual-homed, network isolation proven at the routing layer; host
networking; bind mounts with live file updates; and overlay network research.

**9. Kubernetes Fundamentals** — a three-node kind cluster (v1.37) built from
scratch; every control-plane and node component identified in live `kube-system`
output; first Pod, Deployment and Service; scaling proven not to restart existing
pods; self-healing caught at age 0s; the default-namespace trap.

**10. Kubernetes Core Objects** — all five Pod phases deliberately provoked,
including the live `Error` → `CrashLoopBackOff` flip; a ReplicaSet caught
deleting a pod it never created; and the four deployment strategies **measured
under continuous HTTP load** against a 0-failure baseline — Recreate produced a
5-second total outage, blue-green 0 failures in 1019 requests, canary 90.2/9.8
on a 9:1 replica split.

**11. Kubernetes Services** — all five Service types live side by side, with
MetalLB supplying a real LoadBalancer external IP rather than `<pending>`; a
NodePort proven to answer on a node running none of the pods; ExternalName shown
to have no Endpoints object at all; headless vs ClusterIP reduced to a pure DNS
difference; and Service faults diagnosed by curl exit code.

**12. Ingress, ConfigMaps & Secrets** — the `echo` vs `echo -n` base64 bug proven
byte-for-byte with `xxd`; a mounted ConfigMap measured updating itself after 56
seconds while the env var never did; path- and host-based ingress routing; and
TLS termination including the `-H 'Host:'`-does-not-set-SNI trap.

**13. Storage, HPA & Probes** — emptyDir losing data against a PVC keeping it in
the same experiment; `hostPath` read and written from both sides; dynamic
provisioning with the full four-event chain; a controlled probe experiment where
two identical 40-second-boot containers scored 0 restarts and 4; and an HPA
driven 1 → 3 → 5 → 8 → 10 under real load and back down.

**14. Kubernetes Troubleshooting** — five faults built on purpose
(ImagePullBackOff, CrashLoopBackOff, Pending, OOMKilled, and a Service with a
one-letter selector typo), each diagnosed from evidence, fixed, and verified. A
cluster-wide event sweep also caught unrelated real `SystemOOM` warnings.

**15. Helm** — a chart written by hand rather than scaffolded; templates,
helpers, conditionals and the config-checksum rollout trick; install → upgrade →
rollback across 8 revisions; a **failed upgrade shown leaving a mixed broken
state**, then the same upgrade cleaned up automatically by `--atomic`; packaging;
and a real third-party chart deployed from a public repository.

**16. CI/CD & GitHub Actions** — a Flask calculator API with 16 tests at 100%
coverage; one workflow that tests on five GitHub-hosted runners (three Python
versions, Linux/macOS/Windows), passes artifacts between jobs, builds and
smoke-tests a Docker image, publishes it to GHCR, and deploys it to a kind
cluster created on the runner. A deliberately broken commit shows the failing
tests stopping build, publish and deploy.

**17. Complete CI/CD & DevSecOps** — the spec's flow as ten jobs: build, unit
test, SAST (Semgrep, Bandit), SCA (pip-audit, Trivy), secret scan (Gitleaks),
Docker build, Trivy image scan, a policy-driven **security gate**, push to GHCR,
and deploy to kind under the restricted Pod Security level. An intentionally
insecure commit (command injection, a fake API key, a vulnerable dependency)
was blocked by the gate, then fixed and pushed green.

**18. Terraform & IaC** — an S3 bucket taken through `init → fmt → validate →
plan → apply → show → output → destroy`, verified with the AWS CLI; plus one
README per AWS service (IAM, EC2, S3, VPC, DynamoDB & RDS), each with a small
hands-on run.

**19. Cloud & Terraform in Action** — VPC, public and private subnets, Internet
Gateway, route tables, security group, EC2 with an IAM role, and S3 in one
Terraform project (27 resources). It covers dependencies, state inspection and
change-impact plans, with a rendered `terraform graph` and an architecture
diagram.

**20. Monitoring, Observability & GitOps** — Prometheus, Alertmanager, Grafana,
Loki and Jaeger on kind, with a demo app emitting metrics, logs and traces.
Alerts were driven to FIRING under real load, and an error log was followed to
its trace. Argo CD tracks this repository: a git commit was synced, manual
drift was reverted by self-heal, and a removed resource was pruned.

**21. Final DevOps Project** — TicketHub, a FastAPI + React + PostgreSQL helpdesk
app, taken through the whole chain. A 12-job GitHub Actions pipeline with
DevSecOps scanning and a security gate pushes to GHCR, deploys to kind, and
commits the new image tag to `gitops/`, which Argo CD syncs to a local cluster.
It includes raw manifests and a Helm chart (Ingress, HPA, probes, PVC,
NetworkPolicy), Terraform for VPC/EKS/ECR, and Prometheus/Grafana monitoring
with a firing alert. The troubleshooting challenge has 7 planted faults, each
taken from identify to verified fix.

## Notes on environments

- **AWS / Terraform (18, 19, 21):** no AWS account was used. LocalStack's
  current image refuses to start without a licence token, so Terraform ran
  against [moto](https://github.com/getmoto/moto), a local AWS API emulator.
  Every plan, apply and AWS CLI result is real, but no EC2 instance actually
  boots. Each README shows the provider change needed to target real AWS.
- **CI/CD (16, 17, 21):** GitHub only runs workflows from the repository root,
  so the real workflows live in [`.github/workflows/`](.github/workflows/).
  Each submission folder keeps an identical copy. Kubernetes deployments in CI
  go to a temporary kind cluster created inside the GitHub runner.

## Running things yourself

Each folder's README contains its commands and results. Assignments 09–15 also
include raw evidence transcripts under `evidence/`, and their manifests under
`manifests/`. Cluster setup — including the kind config, the ingress-nginx
controller, metrics-server and MetalLB — is documented in assignment 09 and is a
prerequisite for 10–15; those exercises run in the `default` namespace. The
Docker exercises use host ports in the 9091–9098 range, the multi-stage app uses
8080, and the Kubernetes exercises use 8080/8443 for ingress and 30080/30081 for
NodePorts.
