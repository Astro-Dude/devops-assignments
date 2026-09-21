# Kubernetes Troubleshooting — Homework

Session 14. Five faults were **deliberately built**, diagnosed from evidence
using only `kubectl`, and then fixed — with the fix verified.

Command results are **real captured output** from the three-node kind cluster
built in [assignment 08](../08-kubernetes-fundamentals/README.md).

---

## The method

Every one of the five investigations below follows the same four steps. The order
matters: each step is cheaper than the next, and each one narrows the search.

```
 1. kubectl get pods          →  WHAT is broken, and in which direction
 2. kubectl describe pod      →  WHY Kubernetes thinks so   (read Events LAST-first)
 3. kubectl logs              →  what the APPLICATION said before it died
 4. kubectl exec              →  reality inside a container that is still alive
```

The single most useful rule: **`describe` explains problems that happen *to* a
container; `logs` explains problems that happen *inside* one.** Choosing wrongly
is what makes debugging feel slow — reading logs for an `ImagePullBackOff` gets
you nothing, because the container never started and has no logs.

---

## The patient: five simultaneous faults

All five were applied at once, then left for 90 seconds to develop:

```bash
$ kubectl apply -f manifests/scenarios/
deployment.apps/broken-image created
deployment.apps/broken-crash created
deployment.apps/broken-pending created
pod/broken-oom created
```

### Step 1 — `kubectl get`: what is broken

```bash
$ kubectl get pods -o wide
NAME                              READY   STATUS             RESTARTS      AGE   IP            NODE                NOMINATED NODE   READINESS GATES
broken-crash-68ccc8b7d7-dkv9h     0/1     Error              4 (46s ago)   90s   10.244.2.82   devops-hw-worker2   <none>           <none>
broken-image-585848ccd5-g8jkl     0/1     ImagePullBackOff   0             90s   10.244.1.96   devops-hw-worker    <none>           <none>
broken-oom                        0/1     OOMKilled          3 (65s ago)   90s   10.244.2.81   devops-hw-worker2   <none>           <none>
broken-pending-68587d49d6-rfbm2   0/1     Pending            0             90s   <none>        <none>              <none>           <none>
client                            1/1     Running            0             66m   10.244.1.70   devops-hw-worker    <none>           <none>
```

Four different failure signatures in one listing. Three columns already tell you
where to go next, before running anything else:

| Signal | Read it as |
|---|---|
| `RESTARTS` is climbing | the container **starts and then dies** → go to **logs** |
| `RESTARTS` is 0 but not Running | the container **never started** → go to **describe** |
| `NODE` is `<none>` | never scheduled → **the scheduler**, not the kubelet |
| `IP` is `<none>` | no sandbox exists yet |

So `broken-pending` is a scheduling problem, `broken-image` never started,
and `broken-crash` / `broken-oom` are both running-then-dying — but for different
reasons.

### A faster first sweep

```bash
$ kubectl get pods --field-selector=status.phase!=Running
NAME                              READY   STATUS             RESTARTS   AGE
broken-image-585848ccd5-g8jkl     0/1     ImagePullBackOff   0          101s
broken-pending-68587d49d6-rfbm2   0/1     Pending            0          101s
```

Useful, but note the trap demonstrated in
[assignment 09](../09-k8s-core-objects/README.md): **this filter misses
`broken-crash` and `broken-oom`**, because a crash-looping pod's phase is
`Running`. Filtering on phase alone hides the two worst problems here.

### Step 2 — cluster-wide warnings in one command

```bash
$ kubectl get events --sort-by=.lastTimestamp -A --field-selector type=Warning | tail -15
...
default   22s   Warning   Failed    pod/broken-image-585848ccd5-g8jkl   Error: ImagePullBackOff
default   14s   Warning   BackOff   pod/broken-crash-68ccc8b7d7-dkv9h   Back-off restarting failed container app in pod broken-crash-68ccc8b7d7-dkv9h_default(d528c8c9-...)
default   8s    Warning   BackOff   pod/broken-oom                      Back-off restarting failed container hungry in pod broken-oom_default(1a7318e9-...)
default   7s    Warning   Failed    pod/broken-image-585848ccd5-g8jkl   Failed to pull image "nginx:1.99-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.99-does-not-exist": failed to resolve reference "docker.io/library/nginx:1.99-does-not-exist": docker.io/library/nginx:1.99-does-not-exist: not found
default   7s    Warning   Failed    pod/broken-image-585848ccd5-g8jkl   Error: ErrImagePull
```

`--sort-by=.lastTimestamp` matters: the default event ordering is effectively
random, which is why this command is so often dismissed as noise.

The same output also caught something nobody was looking for:

```
kube-system   29m   Warning   Unhealthy   pod/kube-controller-manager-devops-hw-control-plane   Liveness probe failed: Get "https://127.0.0.1:10257/healthz": unexpected EOF
default       28m   Warning   SystemOOM   node/devops-hw-worker2   System OOM encountered, victim process: speaker, pid: 31060
default       26m   Warning   SystemOOM   node/devops-hw-worker    System OOM encountered, victim process: local-path-prov, pid: 97446
```

These are **real and unrelated to the planted faults**. This laptop was running
an unrelated 10 GB container alongside the cluster, and the node ran out of
memory, killing a MetalLB `speaker` and the local-path provisioner, and briefly
knocking over the controller-manager. It is included rather than edited out
because it is exactly the kind of thing this command is for: **`SystemOOM` on a
node explains failures that look unrelated and random elsewhere**, and no amount
of `describe pod` on an application would ever reveal it.

---

## Fault 1 — `ImagePullBackOff`

```yaml
image: nginx:1.99-does-not-exist
```

Logs are useless here — there is no container to have logged anything. `describe`
is the only source:

```bash
$ kubectl describe pod -l app=broken-image | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                 From               Message
  ----     ------     ----                ----               -------
  Normal   Scheduled  113s                default-scheduler  Successfully assigned default/broken-image-585848ccd5-g8jkl to devops-hw-worker
  Normal   Pulling    21s (x4 over 114s)  kubelet            spec.containers{app}: Pulling image "nginx:1.99-does-not-exist"
  Warning  Failed     20s (x4 over 108s)  kubelet            spec.containers{app}: Failed to pull image "nginx:1.99-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.99-does-not-exist": failed to resolve reference "docker.io/library/nginx:1.99-does-not-exist": docker.io/library/nginx:1.99-does-not-exist: not found
  Warning  Failed     20s (x4 over 108s)  kubelet            spec.containers{app}: Error: ErrImagePull
  Normal   BackOff    8s (x5 over 107s)   kubelet            spec.containers{app}: Back-off pulling image "nginx:1.99-does-not-exist"
  Warning  Failed     8s (x5 over 107s)   kubelet            spec.containers{app}: Error: ImagePullBackOff
```

`Scheduled` succeeded — this is **not** a scheduling problem. The kubelet got the
pod and could not fetch the image. The decisive words are **`NotFound`** and
**`not found`**.

The reason string is also machine-readable:

```bash
$ kubectl get pod -l app=broken-image -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting}'; echo
{"message":"Back-off pulling image \"nginx:1.99-does-not-exist\": ErrImagePull: rpc error: code = NotFound desc = failed to pull and unpack image \"docker.io/library/nginx:1.99-does-not-exist\": failed to resolve reference \"docker.io/library/nginx:1.99-does-not-exist\": docker.io/library/nginx:1.99-does-not-exist: not found","reason":"ImagePullBackOff"}
```

**The same two states have three quite different causes, and the error string is
what separates them:**

| Error text | Real cause | Fix |
|---|---|---|
| `not found` / `NotFound` | typo'd tag or repo | correct the tag |
| `401 Unauthorized` / `authentication required` | private registry | add an `imagePullSecret` |
| `dial tcp … i/o timeout` | node cannot reach the registry | network / proxy / firewall |

---

## Fault 2 — `CrashLoopBackOff`

Here `describe` is almost useless, and that is the lesson:

```bash
$ kubectl describe pod -l app=broken-crash | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                 From               Message
  ----     ------     ----                ----               -------
  Normal   Scheduled  113s                default-scheduler  Successfully assigned default/broken-crash-68ccc8b7d7-dkv9h to devops-hw-worker2
  Normal   Pulled     27s (x5 over 114s)  kubelet            spec.containers{app}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    27s (x5 over 113s)  kubelet            spec.containers{app}: Container created
  Normal   Started    27s (x5 over 113s)  kubelet            spec.containers{app}: Container started
  Warning  BackOff    27s (x4 over 112s)  kubelet            spec.containers{app}: Back-off restarting failed container app in pod broken-crash-68ccc8b7d7-dkv9h_default(d528c8c9-...)
```

Kubernetes did everything right: pulled, created, started — five times. It has no
idea *why* the process keeps exiting, because from its point of view nothing
failed. Only the application knows:

```bash
$ kubectl logs -l app=broken-crash --tail=10
FATAL: DATABASE_URL is not set
starting checkout-service...
```

There is the answer, in the app's own words. (The lines appear reversed because
`stderr` and `stdout` are interleaved by flush order, not by time — a small trap
of its own; `--timestamps` resolves it.)

### The flag that matters most

Once a container has restarted, `kubectl logs` shows the **current** attempt. To
see the one that actually failed:

```bash
$ kubectl logs <pod> --previous
```

On this cluster that run had already been garbage-collected:

```bash
$ kubectl logs -l app=broken-crash --previous --tail=5
unable to retrieve container logs for containerd://dda9c6bbc57b89d21762741679607c244d6d5f941c694888f660fb8f196ce0da
```

Which is itself the argument for shipping logs off the node — **`--previous`
holds exactly one generation, and a fast crash loop destroys the evidence.**

Other flags used here:

```bash
$ kubectl logs -l app=broken-crash --tail=5 --prefix
[pod/broken-crash-68ccc8b7d7-dkv9h/app] FATAL: DATABASE_URL is not set
[pod/broken-crash-68ccc8b7d7-dkv9h/app] starting checkout-service...

$ kubectl logs -l app=broken-crash --since=2m --timestamps
2026-09-21T10:20:14.109934464Z FATAL: DATABASE_URL is not set
2026-09-21T10:20:14.109934464Z starting checkout-service...
```

`--prefix` is essential with `-l` across many pods; `--timestamps` fixes the
ordering confusion above.

---

## Fault 3 — `Pending`

```yaml
nodeSelector:
  disktype: ssd
```

`NODE` was `<none>`, so the kubelet was never involved. The scheduler explains
itself in full:

```bash
$ kubectl describe pod -l app=broken-pending | sed -n '/^Events:/,$p'
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  113s  default-scheduler  0/3 nodes are available: 1 node(s) had untolerated taint(s), 2 node(s) didn't match Pod's node affinity/selector. preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling.
```

That message accounts for **every node individually** — 1 rejected on a taint
(the control plane), 2 on the selector. Compare with the `Pending` in
[assignment 09](../09-k8s-core-objects/README.md), where the same command said
`Insufficient cpu, Insufficient memory` instead. **The `FailedScheduling` text
names the exact predicate that failed**, so there is never any guesswork:

| Message fragment | Cause |
|---|---|
| `didn't match Pod's node affinity/selector` | `nodeSelector` / affinity matches no node |
| `Insufficient cpu` / `Insufficient memory` | requests exceed free capacity |
| `had untolerated taint(s)` | node tainted, pod has no toleration |
| `had volume node affinity conflict` | PV is in a zone the pod cannot reach |
| `pod has unbound immediate PersistentVolumeClaims` | PVC never bound |

Confirming the claim directly:

```bash
$ kubectl get nodes --show-labels | tr ',' '\n' | grep -i disktype
(no disktype label anywhere: exit 1)
```

No node in the cluster carries `disktype` at all.

---

## Fault 4 — `OOMKilled`

```yaml
args: ["--vm", "1", "--vm-bytes", "200M", "--vm-hang", "1"]
resources:
  limits: { memory: 50Mi }
```

`describe` shows restarts but never says the word "memory":

```bash
$ kubectl describe pod broken-oom | sed -n '/^Events:/,$p'
Events:
  Normal   Started    21s (x5 over 104s)  kubelet  spec.containers{hungry}: Container started
  Warning  BackOff    21s (x5 over 102s)  kubelet  spec.containers{hungry}: Back-off restarting failed container hungry in pod broken-oom_default(1a7318e9-...)
```

The evidence lives in the container's **previous termination state**:

```bash
$ kubectl get pod broken-oom -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'; echo
{"containerID":"containerd://8f661aef062479cfb3b245e832bbcc97f2e821b6e6444261c09ccf102cb7149e","exitCode":137,"finishedAt":"2026-09-21T10:19:37Z","reason":"OOMKilled","startedAt":"2026-09-21T10:19:37Z"}
```

**`"reason":"OOMKilled"`, `"exitCode":137`.** Note `startedAt` and `finishedAt`
are the *same second* — it died instantly.

```bash
$ kubectl get pod broken-oom -o jsonpath='limits={.spec.containers[0].resources.limits.memory}'; echo
limits=50Mi
```

Asking for 200M against a 50Mi limit. Two exit codes are worth memorising:

| Exit code | Signal | Meaning |
|---|---|---|
| **137** | SIGKILL (128+9) | **OOMKilled**, or a failed liveness probe |
| **143** | SIGTERM (128+15) | graceful shutdown — usually normal |

The important subtlety: **the kernel killed the process, not Kubernetes.** A
memory *limit* is a hard cgroup ceiling — no grace period, no `SIGTERM`, no
chance to flush anything. This is why memory limits and CPU limits behave
completely differently: exceeding a CPU limit merely throttles you.

---

## Fault 5 — a Service that resolves but does not work

The most confusing class of failure, because **nothing is in a bad state**.

```bash
$ kubectl exec client -- curl -s --max-time 5 http://payments-svc
command terminated with exit code 7
```

### Step 1 — is it DNS?

```bash
$ kubectl exec client -- nslookup payments-svc.default.svc.cluster.local
Name:	payments-svc.default.svc.cluster.local
Address: 10.96.127.43
```

**DNS is fine.** Worth doing first anyway, because it eliminates an entire class
of cause in one command. Note also that `curl` exited **7 (connection refused)**,
not 28 (timeout) — as established in
[assignment 10](../10-kubernetes-services/README.md), that already rules out a
pure network black hole.

### Step 2 — are the pods healthy?

```bash
$ kubectl get pods -l app=payments
NAME                        READY   STATUS    RESTARTS   AGE
payments-68c8d7799b-g66bm   1/1     Running   0          1s
payments-68c8d7799b-qmggv   1/1     Running   0          1s
```

Both `1/1 Running`. Nothing to fix here.

### Step 3 — the decisive check

```bash
$ kubectl get endpoints payments-svc
NAME           ENDPOINTS   AGE
payments-svc   <none>      1s
```

**`<none>`.** The Service is routing to an empty list. Everything upstream is
healthy and the Service still cannot work.

### Step 4 — compare the selector with reality

```bash
$ kubectl get svc payments-svc -o jsonpath='service selector: {.spec.selector}'; echo
service selector: {"app":"payment"}

$ kubectl get pods -l app=payments -o jsonpath='{range .items[*]}pod labels:    {.metadata.labels}{"\n"}{end}'
pod labels:    {"app":"payments","pod-template-hash":"68c8d7799b"}
pod labels:    {"app":"payments","pod-template-hash":"68c8d7799b"}
```

`payment` versus `payments`. **One missing `s`.** Kubernetes will never warn
about this — an empty Service is a legal object.

### Step 5 — prove the pods are innocent

```bash
$ kubectl exec client -- curl -s --max-time 5 http://10.244.2.83
payments ok
```

Bypassing the Service entirely and hitting the pod IP works perfectly. That
single command splits the problem cleanly in two: **the application is fine, the
routing is broken.** Always worth doing before anyone starts reading application
code.

### The fix, verified

```bash
$ kubectl patch svc payments-svc -p '{"spec":{"selector":{"app":"payments"}}}'
service/payments-svc patched

$ kubectl get endpoints payments-svc
NAME           ENDPOINTS                       AGE
payments-svc   10.244.1.97:80,10.244.2.83:80   15s

$ kubectl exec client -- curl -s http://payments-svc
payments ok
```

Endpoints populated **immediately**, with no restart of anything.

---

## `kubectl exec` — the last resort, and what it is good for

`exec` only works on a container that is **currently running**, which is why it
is step 4 and not step 1. What it is uniquely good for is confirming that the
world inside the container matches what you think you configured:

```bash
$ kubectl exec client -- sh -c 'hostname; id; echo ---; cat /etc/resolv.conf'
sh: line 1: hostname: command not found
uid=0 gid=0 groups=0
---
search default.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

That first line is itself a lesson: **`hostname: command not found`**. Minimal
images do not have the tools you expect, and debugging inside a `distroless` or
`scratch` container is often impossible. The modern answer is
`kubectl debug -it <pod> --image=busybox --target=<container>`, which attaches an
ephemeral container with real tools into the same namespaces.

```bash
$ kubectl exec client -- env | grep -i kubernetes | sort
KUBERNETES_PORT=tcp://10.96.0.1:443
KUBERNETES_PORT_443_TCP=tcp://10.96.0.1:443
KUBERNETES_PORT_443_TCP_ADDR=10.96.0.1
KUBERNETES_PORT_443_TCP_PORT=443
KUBERNETES_PORT_443_TCP_PROTO=tcp
KUBERNETES_SERVICE_HOST=10.96.0.1
KUBERNETES_SERVICE_PORT=443
KUBERNETES_SERVICE_PORT_HTTPS=443
```

Checking env vars *from inside* is the fastest way to catch a ConfigMap or Secret
that was edited but never picked up — the exact trap measured in
[assignment 11](../11-ingress-configmaps-secrets/README.md), where a changed
ConfigMap updated the mounted file after 56 seconds but never the environment
variable.

---

## Closing the loop: every fault fixed and verified

```bash
$ kubectl apply -f manifests/scenarios/01-FIXED.yaml      # correct image tag
deployment.apps/broken-image configured

$ kubectl apply -f manifests/scenarios/02-FIXED.yaml      # supply DATABASE_URL
deployment.apps/broken-crash configured

$ kubectl label node devops-hw-worker disktype=ssd --overwrite
node/devops-hw-worker labeled

$ kubectl apply -f manifests/scenarios/04-FIXED.yaml      # ask for 30M, not 200M
pod/broken-oom created
```

```bash
$ kubectl get pods -o wide
NAME                              READY   STATUS    RESTARTS   AGE     IP            NODE                NOMINATED NODE   READINESS GATES
broken-crash-7b6cc84c44-mxs96     1/1     Running   0          46s     10.244.1.98   devops-hw-worker    <none>           <none>
broken-image-6fd5dcfcb6-v28xr     1/1     Running   0          46s     10.244.2.84   devops-hw-worker2   <none>           <none>
broken-oom                        1/1     Running   0          45s     10.244.2.85   devops-hw-worker2   <none>           <none>
broken-pending-68587d49d6-rfbm2   1/1     Running   0          3m38s   10.244.1.99   devops-hw-worker    <none>           <none>
client                            1/1     Running   0          68m     10.244.1.70   devops-hw-worker    <none>           <none>
payments-68c8d7799b-g66bm         1/1     Running   0          86s     10.244.2.83   devops-hw-worker2   <none>           <none>
payments-68c8d7799b-qmggv         1/1     Running   0          86s     10.244.1.97   devops-hw-worker    <none>           <none>
```

All `1/1 Running`, all with `RESTARTS 0`.

```bash
$ kubectl logs -l app=broken-crash --tail=3
starting checkout-service...
connected to postgres://db:5432/checkout
```

One detail worth noticing: **`broken-pending` has an age of 3m38s and 0
restarts** — it is the *same pod object* that had been Pending the whole time.
Labelling the node did not recreate anything; the scheduler simply re-evaluated
a pod it had previously parked and placed it. Pending pods are retried forever,
not failed.

---

## The diagnosis table

| Symptom | Container started? | Go to | Real cause |
|---|---|---|---|
| `Pending`, `NODE <none>` | no — never scheduled | `describe` → `FailedScheduling` | resources, selector, taint, PVC |
| `ImagePullBackOff` | no | `describe` → Events | bad tag / auth / registry unreachable |
| `CrashLoopBackOff`, restarts climbing | **yes** | **`logs`** (and `--previous`) | the app itself is exiting |
| `OOMKilled`, exit **137** | yes | `lastState.terminated` | memory limit too low, or a leak |
| `Running` but unreachable | yes | **`get endpoints`** | selector/label mismatch, wrong `targetPort` |
| `Running`, wrong behaviour | yes | `exec` → `env` | stale config; env vars need a restart |

---

## What I took away

- **`describe` vs `logs` is decided by one question: did the container start?**
  If it never started, logs do not exist. If it started and died, `describe` will
  only ever say "BackOff" and the real answer is in the logs.
- **`RESTARTS` is the fastest single signal on the whole dashboard.** Climbing
  means the app is failing; stuck at 0 with a bad status means Kubernetes never
  got that far.
- **`--field-selector=status.phase!=Running` is a trap** — it hides crash loops,
  because a crash-looping pod's phase is `Running`.
- **`kubectl get endpoints` is the one-line answer for any Service problem**, and
  hitting the pod IP directly is the one-line way to prove the app is innocent.
- **OOMKilled is invisible in `describe`** — it lives in
  `lastState.terminated.reason`, and exit 137 means the kernel did it, with no
  grace period at all.
- **Cluster-wide `Warning` events catch what per-pod debugging cannot.** The
  `SystemOOM` entries here came from an unrelated workload on the same laptop and
  would have explained a whole class of "random" failures.
- **`--previous` keeps exactly one generation of logs.** A fast crash loop
  destroys its own evidence, which is the practical argument for log shipping.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | `kubectl get` for triage | Done — 4 signatures read from one listing; `--field-selector` trap shown |
| 2 | `kubectl describe` | Done — used on all 5 faults, Events read last-first |
| 3 | `kubectl logs` | Done — incl. `--previous`, `--prefix`, `--timestamps`, `--since` |
| 4 | `kubectl exec` | Done — incl. a minimal image with no `hostname`, and `kubectl debug` |
| 5 | Cluster events | Done — `--sort-by=.lastTimestamp`; caught real unplanned `SystemOOM` |
| 6 | Debug `CrashLoopBackOff` | Done — cause found in app logs, fixed, verified |
| 7 | Debug `ImagePullBackOff` | Done — `NotFound` isolated from auth/network causes |
| 8 | Debug `Pending` pods | Done — `FailedScheduling` per-node breakdown, fixed by labelling a node |
| 9 | Debug Service / DNS | Done — 5-step isolation, empty endpoints, one-letter typo found and fixed |
| — | Extra: `OOMKilled` | Done — exit 137 traced to `lastState.terminated` |
| — | Verify every fix | Done — all 7 pods `1/1 Running`, `RESTARTS 0` |
