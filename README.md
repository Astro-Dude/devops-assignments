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

## Running things yourself

Each folder's README contains its commands and results. Assignments 08–14 also
include raw evidence transcripts. Kubernetes setup is in assignment 08; the
troubleshooting and Helm exercises use separate namespaces. The Docker exercises use host ports in the 9091–9098 range, and the
multi-stage app uses 8080.
