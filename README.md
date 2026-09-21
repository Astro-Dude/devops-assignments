# DevOps Assignments

Homework submissions for the DevOps course, covering Linux, shell scripting,
networking, Git, Docker, Kubernetes, and Helm.

All documentation in this repository contains **real captured command output**
from live systems — not sample or illustrative text. Linux exercises were run
in an Ubuntu 22.04 container with systemd enabled; Docker exercises were run on
a live Docker engine. Docker web applications have browser screenshots; the
Kubernetes and Helm submissions include captured CLI and HTTP checks.

## Contents

| # | Topic | Submission |
|---|---|---|
| 1 | Linux Fundamentals | [DevOps/01-linux-fundamentals](DevOps/01-linux-fundamentals/README.md) |
| 2 | Shell Scripting | [DevOps/02-shell-scripting](DevOps/02-shell-scripting/README.md) |
| 3 | Networking Fundamentals | [DevOps/03-networking](DevOps/03-networking/README.md) |
| 4 | Git / GitHub | [DevOps/04-git-github](DevOps/04-git-github/README.md) |
| 5 | Docker Fundamentals | [DevOps/05-docker-fundamentals](DevOps/05-docker-fundamentals/README.md) |
| 6 | Dockerfiles & Images | [DevOps/06-dockerfiles-images](DevOps/06-dockerfiles-images/README.md) |
| 7 | Docker Networking | [DevOps/07-docker-network](DevOps/07-docker-network/README.md) |
| 8 | Kubernetes Fundamentals | [DevOps/08-kubernetes-fundamentals](DevOps/08-kubernetes-fundamentals/README.md) |
| 9 | Kubernetes Core Objects | [DevOps/09-k8s-core-objects](DevOps/09-k8s-core-objects/README.md) |
| 10 | Kubernetes Services | [DevOps/10-kubernetes-services](DevOps/10-kubernetes-services/README.md) |
| 11 | Ingress, ConfigMaps & Secrets | [DevOps/11-ingress-configmaps-secrets](DevOps/11-ingress-configmaps-secrets/README.md) |
| 12 | Storage, HPA & Probes | [DevOps/12-storage-hpa-probes](DevOps/12-storage-hpa-probes/README.md) |
| 13 | Kubernetes Troubleshooting | [DevOps/13-kubernetes-troubleshooting](DevOps/13-kubernetes-troubleshooting/README.md) |
| 14 | Helm | [DevOps/14-helm](DevOps/14-helm/README.md) |

Course sessions 9–15 map to assignments 08–14. The course has 15 sessions;
this repository has 14 submissions because the earlier session grouping differs.
Source: [devops-heros](https://github.com/Nency-Ravaliya/devops-heros),
reviewed at commit `f25086a66daf1465336e4daeb0ce4cff1e0ac3c9`.

## What each one covers

**1. Linux Fundamentals** — soft vs hard links demonstrated through inode and
link-count evidence; `adduser` vs `useradd` compared by actually creating users
with both; `journalctl` practised against a real systemd journal, including
locating a genuine nginx config error by file and line; a ~90-command cheat
sheet with output.

**2. Shell Scripting** — a system information script using variables,
`read -p`, `mkdir`, `touch`, `df`, `ps` and `>` redirection, with transcripts of
both a custom-input run and a defaults run.

**3. Networking** — 10 sections covering interfaces, routing, ARP, `ping`,
`traceroute`/`mtr`, DNS, sockets, port testing, `curl`/`wget`, `tcpdump` and
`whois`, each with output and an explanation of what it means.

**4. Git / GitHub** — `git commit -m` vs `git commit -a -m` across five
scenarios including the untracked-file trap; a full cherry-pick exercise moving
one commit between branches.

**5. Docker Fundamentals** — six Hello World web apps (Node.js, Python, Java,
Apache, React, Nginx), each with its own Dockerfile, built, run, and verified
with browser screenshots.

**6. Dockerfiles & Images** — a multi-stage build serving *Hello World from
Docker multi-stage build* on port 8080, with a measured size comparison against
the single-stage equivalent.

**7. Docker Networking** — a three-tier topology across three networks with the
backend dual-homed, network isolation proven at the routing layer; host
networking; bind mounts with live file updates; and overlay network research.

**8. Kubernetes Fundamentals** — a three-node kind cluster (v1.37) built from
scratch; every control-plane and node component identified in live `kube-system`
output; first Pod, Deployment and Service; scaling proven not to restart existing
pods; self-healing caught at age 0s; the default-namespace trap.

**9. Kubernetes Core Objects** — all five Pod phases deliberately provoked,
including the live `Error` → `CrashLoopBackOff` flip; a ReplicaSet caught
deleting a pod it never created; and the four deployment strategies **measured
under continuous HTTP load** against a 0-failure baseline — Recreate produced a
5-second total outage, blue-green 0 failures in 1019 requests, canary 90.2/9.8
on a 9:1 replica split.

**10. Kubernetes Services** — all five Service types live side by side, with
MetalLB supplying a real LoadBalancer external IP rather than `<pending>`; a
NodePort proven to answer on a node running none of the pods; ExternalName shown
to have no Endpoints object at all; headless vs ClusterIP reduced to a pure DNS
difference; and Service faults diagnosed by curl exit code.

**11. Ingress, ConfigMaps & Secrets** — the `echo` vs `echo -n` base64 bug proven
byte-for-byte with `xxd`; a mounted ConfigMap measured updating itself after 56
seconds while the env var never did; path- and host-based ingress routing; and
TLS termination including the `-H 'Host:'`-does-not-set-SNI trap.

**12. Storage, HPA & Probes** — emptyDir losing data against a PVC keeping it in
the same experiment; `hostPath` read and written from both sides; dynamic
provisioning with the full four-event chain; a controlled probe experiment where
two identical 40-second-boot containers scored 0 restarts and 4; and an HPA
driven 1 → 3 → 5 → 8 → 10 under real load and back down.

**13. Kubernetes Troubleshooting** — five faults built on purpose
(ImagePullBackOff, CrashLoopBackOff, Pending, OOMKilled, and a Service with a
one-letter selector typo), each diagnosed from evidence, fixed, and verified. A
cluster-wide event sweep also caught unrelated real `SystemOOM` warnings.

**14. Helm** — a chart written by hand rather than scaffolded; templates,
helpers, conditionals and the config-checksum rollout trick; install → upgrade →
rollback across 8 revisions; a **failed upgrade shown leaving a mixed broken
state**, then the same upgrade cleaned up automatically by `--atomic`; packaging;
and a real third-party chart deployed from a public repository.

## Running things yourself

Each folder's README contains its commands and results. Assignments 08–14 also
include raw evidence transcripts under `evidence/`, and their manifests under
`manifests/`. Cluster setup — including the kind config, the ingress-nginx
controller, metrics-server and MetalLB — is documented in assignment 08 and is a
prerequisite for 09–14; those exercises run in the `default` namespace. The
Docker exercises use host ports in the 9091–9098 range, the multi-stage app uses
8080, and the Kubernetes exercises use 8080/8443 for ingress and 30080/30081 for
NodePorts.
