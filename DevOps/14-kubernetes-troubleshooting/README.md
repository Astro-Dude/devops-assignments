# Kubernetes Troubleshooting — Homework

Session 14. Five faults were **deliberately built**, diagnosed from evidence
using only `kubectl`, and then fixed — with the fix verified.

Command results are **real captured output** from the three-node kind cluster
built in [session 09](../09-kubernetes-fundamentals/README.md).

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
[session 10](../10-k8s-core-objects/README.md): **this filter misses
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
[session 10](../10-k8s-core-objects/README.md), where the same command said
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
[session 11](../11-kubernetes-services/README.md), that already rules out a
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
[session 12](../12-ingress-configmaps-secrets/README.md), where a changed
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

## Task 1, completed — `kubectl events`, `kubectl explain`, `kubectl top`, `get -o wide`

The spec's command list has eight entries. `get`, `describe`, `logs` and `exec`
are used throughout this page. The other four were captured separately on a
single-node kind cluster (`hw-legacy`), in a scratch namespace `s14-gap`.
Transcript: [`evidence/s14-gap-commands.txt`](evidence/s14-gap-commands.txt) and
[`evidence/s14-gap-issues.txt`](evidence/s14-gap-issues.txt).

### `kubectl get -o wide` — where is it, and what is its IP?

```console
$ kubectl -n s14-gap get pods -o wide
NAME              READY   STATUS    RESTARTS   AGE    IP            NODE                      NOMINATED NODE   READINESS GATES
api-config        1/1     Running   0          49s    10.244.0.72   hw-legacy-control-plane   <none>           <none>
client            1/1     Running   0          2m8s   10.244.0.65   hw-legacy-control-plane   <none>           <none>
orders            1/1     Running   0          32s    10.244.0.74   hw-legacy-control-plane   <none>           <none>
registry-typo     1/1     Running   0          82s    10.244.0.70   hw-legacy-control-plane   <none>           <none>
web-with-config   1/1     Running   0          82s    10.244.0.71   hw-legacy-control-plane   <none>           <none>

$ kubectl get nodes -o wide
NAME                      STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                       KERNEL-VERSION            CONTAINER-RUNTIME
hw-legacy-control-plane   Ready    control-plane   26m   v1.37.0   172.18.0.3    <none>        Debian GNU/Linux 13 (trixie)   7.0.12-linuxkit (arm64)   containerd://2.3.4
```

`-o wide` adds the pod IP and node. The pod IP is what the networking test
below connects to directly. For nodes it also shows the runtime and kernel.

### `kubectl top` — who is using the CPU right now

```console
$ kubectl top nodes
NAME                      CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
hw-legacy-control-plane   5856m        39%      1406Mi          8%          

$ kubectl top pods -A --sort-by=cpu | head -8
NAMESPACE            NAME                                              CPU(cores)   MEMORY(bytes)   
s13-hpa              load-generator-7c686fd77b-jhl5q                   791m         9Mi             
s13-hpa              load-generator-7c686fd77b-x2gkc                   768m         3Mi             
s13-hpa              load-generator-7c686fd77b-x92p6                   762m         3Mi             
s13-hpa              load-generator-7c686fd77b-nwxzg                   757m         2Mi             
production-webapp    load-generator                                    747m         6Mi             
kube-system          coredns-559f6c778d-mps4k                          413m         31Mi            
kube-system          coredns-559f6c778d-5bxcs                          271m         44Mi            

$ kubectl top pod -n kube-system -l k8s-app=kube-dns --containers
POD                        NAME      CPU(cores)   MEMORY(bytes)   
coredns-559f6c778d-5bxcs   coredns   271m         44Mi            
coredns-559f6c778d-mps4k   coredns   413m         31Mi            
```

This came out more useful than I expected. Session 13's HPA load test was
running on the same cluster at the time, and `top` showed both the cause and a
side effect:

- the busy-looping load generators were at about 0.76 cores each;
- **CoreDNS was using 0.4 cores**. Every `wget http://service` in those loops
  does a DNS lookup first (and, with `ndots:5`, goes through the search list),
  so load on an app also becomes load on cluster DNS.

`top` needs metrics-server. It shows usage, not requests or limits, so it
complements `describe node`'s "Allocated resources".

### `kubectl explain` — the API documentation, offline

```console
$ kubectl explain pod.spec.containers.livenessProbe | head -25
KIND:       Pod
VERSION:    v1

FIELD: livenessProbe <Probe>

DESCRIPTION:
    Periodic probe of container liveness. Container will be restarted if the
    probe fails. Cannot be updated. ...
FIELDS:
  exec	<ExecAction>
  failureThreshold	<integer>
    Minimum consecutive failures for the probe to be considered failed after
    having succeeded. Defaults to 3. Minimum value is 1.
  grpc	<GRPCAction>
  httpGet	<HTTPGetAction>

$ kubectl explain deployment.spec.strategy.rollingUpdate
FIELD: rollingUpdate <RollingUpdateDeployment>
FIELDS:
  maxSurge	<IntOrString>
    The maximum number of pods that can be scheduled above the desired number of
    pods. ... This can not be 0 if MaxUnavailable is 0. ... Defaults to 25%.
  maxUnavailable	<IntOrString>
    The maximum number of pods that can be unavailable during the update. ...
    Defaults to 25%.

$ kubectl explain pod.spec.containers.resources --recursive | head -20
FIELD: resources <ResourceRequirements>
FIELDS:
  claims	<[]ResourceClaim>
    name	<string> -required-
    request	<string>
  limits	<map[string]Quantity>
  requests	<map[string]Quantity>
```

`explain` answers "what is this field called, where does it go, and what is
the default" from the API server's own schema, for the exact version running.
It is how you fix a misspelled or misplaced field in a broken manifest without
leaving the terminal. `--recursive` prints the whole subtree.

### `kubectl events` — the newer events command

Session 14's first run used `kubectl get events`. `kubectl events` is the
dedicated command. It sorts by time by default, `--for` filters to one object,
and `--types` filters by severity:

```console
$ kubectl events -n s14-gap --types=Warning
LAST SEEN            TYPE      REASON        OBJECT                MESSAGE
107s                 Warning   Failed        Pod/registry-typo     Error: ImagePullBackOff
96s (x2 over 107s)   Warning   Failed        Pod/registry-typo     Failed to pull image "registry.example.invalid/team/web:1.0": ... no such host
96s (x2 over 107s)   Warning   Failed        Pod/registry-typo     Error: ErrImagePull
66s (x6 over 82s)    Warning   FailedMount   Pod/web-with-config   MountVolume.SetUp failed for volume "site-config" : configmap "web-site-config" not found
48s (x2 over 49s)    Warning   Failed        Pod/api-config        Error: couldn't find key password in Secret s14-gap/api-db

$ kubectl events -n s14-gap --for pod/web-with-config
LAST SEEN           TYPE      REASON        OBJECT                MESSAGE
33s                 Normal    Scheduled     Pod/web-with-config   Successfully assigned s14-gap/web-with-config to hw-legacy-control-plane
17s (x6 over 33s)   Warning   FailedMount   Pod/web-with-config   MountVolume.SetUp failed for volume "site-config" : configmap "web-site-config" not found
0s                  Normal    Pulled        Pod/web-with-config   Container image "nginx:1.27" already present on machine ...
0s                  Normal    Created       Pod/web-with-config   Container created
0s                  Normal    Started       Pod/web-with-config   Container started
```

One `--types=Warning` call lists the root cause of three of the five issues
below, each in a single line.

---

## More issues: ErrImagePull, ContainerCreating, configuration, DNS, pod networking

The spec lists nine issue types. Five faults above cover `ImagePullBackOff`,
`CrashLoopBackOff`, `Pending`, `OOMKilled` and a Service with no endpoints. The
remaining types were built and fixed on `hw-legacy` in namespace `s14-gap`.
Manifests are in [`manifests/more-issues/`](manifests/more-issues/). Every
issue follows the same steps: identify, investigate, root cause, fix, verify.

### Issue A — `ErrImagePull` (the registry does not exist)

**Identify.** [`01-errimagepull-registry.yaml`](manifests/more-issues/01-errimagepull-registry.yaml),
sampled every 4 s:

```console
[+4s] registry-typo   0/1   ErrImagePull       0     4s
[+8s] registry-typo   0/1   ErrImagePull       0     8s
[+12s] registry-typo   0/1   ImagePullBackOff   0     12s
```

**Investigate.**

```console
$ kubectl events -n s14-gap --for pod/registry-typo --types=Warning
Warning   Failed   Pod/registry-typo   Failed to pull image "registry.example.invalid/team/web:1.0": failed to pull and unpack image
  "registry.example.invalid/team/web:1.0": failed to resolve reference "registry.example.invalid/team/web:1.0": failed to do request:
  Head "https://registry.example.invalid/v2/team/web/manifests/1.0": dial tcp: lookup registry.example.invalid on 192.168.65.254:53: no such host
Warning   Failed   Pod/registry-typo   Error: ErrImagePull
Warning   Failed   Pod/registry-typo   Error: ImagePullBackOff
```

**Root cause.** `ErrImagePull` is the status of a pull attempt that just
failed. `ImagePullBackOff` is the kubelet waiting longer and longer before it
tries again. They are two stages of the same problem. The message says *why*,
and here it differs from Fault 1. Fault 1 got `code = NotFound` (the registry
answered, the tag doesn't exist). Here it is `lookup … no such host`: the
**node** could not resolve the registry hostname at all (note the resolver is
the node's, `192.168.65.254`, not CoreDNS). Possible causes are a typo in the
registry name, a private registry missing from DNS, or a node with no egress.
Auth problems show up as `401 Unauthorized` instead.

**Fix and verify.** Use an image from a real registry
([`01-FIXED.yaml`](manifests/more-issues/01-FIXED.yaml)). The image field cannot
be edited on a running pod, so the pod is deleted and recreated:

```console
$ kubectl -n s14-gap delete pod registry-typo --wait=true
$ kubectl -n s14-gap apply -f manifests/more-issues/01-FIXED.yaml
$ kubectl -n s14-gap get pod registry-typo
NAME            READY   STATUS    RESTARTS   AGE
registry-typo   1/1     Running   0          0s
```

### Issue B — stuck in `ContainerCreating`

**Identify.** [`02-containercreating.yaml`](manifests/more-issues/02-containercreating.yaml),
20 s after creation:

```console
$ kubectl -n s14-gap get pod web-with-config -o wide
NAME              READY   STATUS              RESTARTS   AGE   IP       NODE                      ...
web-with-config   0/1     ContainerCreating   0          20s   <none>   hw-legacy-control-plane
```

It has a node, so scheduling worked, but it has no IP and no container.

**Investigate.**

```console
$ kubectl -n s14-gap describe pod web-with-config
Status:           Pending
Conditions:
  PodReadyToStartContainers   False 
  Initialized                 True 
  PodScheduled                True 
Events:
  Normal   Scheduled    20s               default-scheduler  Successfully assigned s14-gap/web-with-config to hw-legacy-control-plane
  Warning  FailedMount  4s (x6 over 20s)  kubelet            MountVolume.SetUp failed for volume "site-config" : configmap "web-site-config" not found

$ kubectl -n s14-gap logs web-with-config
Error from server (BadRequest): container "web" in pod "web-with-config" is waiting to start: ContainerCreating

$ kubectl -n s14-gap get configmap web-site-config
Error from server (NotFound): configmaps "web-site-config" not found
```

**Root cause.** The pod mounts a ConfigMap that does not exist. The kubelet
keeps retrying the mount (`x6`) and never creates the container, so there are
no logs. `PodReadyToStartContainers False` means the sandbox and volumes are
not ready. Other common causes of a stuck `ContainerCreating` are a missing
Secret, a PVC that won't attach, and CNI failing to assign an IP.

**Fix and verify.** Create the ConfigMap
([`02-FIXED-configmap.yaml`](manifests/more-issues/02-FIXED-configmap.yaml)). The
pod was **not** recreated: the kubelet's next mount retry succeeded.

```console
$ kubectl -n s14-gap apply -f manifests/more-issues/02-FIXED-configmap.yaml
configmap/web-site-config created

$ kubectl -n s14-gap get pod web-with-config
NAME              READY   STATUS    RESTARTS   AGE
web-with-config   1/1     Running   0          33s

$ kubectl -n s14-gap exec client -- wget -q -O- http://<web-with-config pod IP>
config mounted OK
```

`config mounted OK` comes from the nginx config inside the new ConfigMap, so
the volume really is mounted.

### Issue C — configuration error: `CreateContainerConfigError`

**Identify.**

```console
$ kubectl -n s14-gap get pod api-config
NAME         READY   STATUS                       RESTARTS   AGE
api-config   0/1     CreateContainerConfigError   0          10s
```

**Investigate.**

```console
$ kubectl -n s14-gap describe pod api-config
    State:          Waiting
      Reason:       CreateContainerConfigError
    Environment:
      DB_HOST:      postgres.s14-gap.svc.cluster.local
      DB_PASSWORD:  <set to the key 'password' in secret 'api-db'>  Optional: false
Events:
  Warning  Failed     9s (x2 over 10s)  kubelet  spec.containers{api}: Error: couldn't find key password in Secret s14-gap/api-db

$ kubectl -n s14-gap get secret api-db -o jsonpath='{.data}'
{"passwd":"bGFiLW9ubHktZGVtbw=="}
```

**Root cause.** The Secret exists but its key is `passwd`, while the pod asks
for `password`. The image was pulled fine and the scheduler was happy. The
kubelet just could not build the container's environment. A missing ConfigMap
or Secret referenced by `env`/`envFrom` gives the same status. A missing
*volume* source gives Issue B's `ContainerCreating` instead.

**Fix and verify.** Correct the key name
([`03-FIXED-secret.yaml`](manifests/more-issues/03-FIXED-secret.yaml)). Again
the pod recovered by itself on the next retry:

```console
$ kubectl -n s14-gap apply -f manifests/more-issues/03-FIXED-secret.yaml
secret/api-db configured

$ kubectl -n s14-gap get pod api-config
NAME         READY   STATUS    RESTARTS   AGE
api-config   1/1     Running   0          14s

$ kubectl -n s14-gap logs api-config
DB_HOST=postgres.s14-gap.svc.cluster.local
password length=13
```

### Issue D — DNS: a short name that only works in one namespace

**Identify.** A client in `s14-gap` calls `http://backend`. The backend runs in
`s14-gap-b` ([`04-dns-backend.yaml`](manifests/more-issues/04-dns-backend.yaml)).

```console
$ kubectl -n s14-gap exec client -- wget -T 3 -q -O- http://backend
wget: bad address 'backend'
command terminated with exit code 1
```

`bad address` means name resolution failed before any connection was tried.

**Investigate.**

```console
$ kubectl -n s14-gap exec client -- nslookup backend        (A and AAAA answers interleaved; duplicates removed)
Server:		10.96.0.10
Address:	10.96.0.10:53
** server can't find backend.s14-gap.svc.cluster.local: NXDOMAIN
** server can't find backend.svc.cluster.local: NXDOMAIN
** server can't find backend.cluster.local: NXDOMAIN

$ kubectl -n s14-gap exec client -- cat /etc/resolv.conf
search s14-gap.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5

$ kubectl get svc -A -l '!component' --field-selector metadata.name=backend
NAMESPACE   NAME      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
s14-gap-b   backend   ClusterIP   10.96.112.195   <none>        80/TCP    1s
```

**Root cause.** CoreDNS is answering (the server is `10.96.0.10` and replies
come back), so DNS itself is fine. The name is wrong. The search list expanded
`backend` to `backend.s14-gap.svc.cluster.local`, i.e. **the client's own
namespace**, and no Service called `backend` exists there. The Service is in
`s14-gap-b`.

**Fix and verify.** Use `<service>.<namespace>` or the full FQDN:

```console
$ kubectl -n s14-gap exec client -- wget -T 3 -q -O- http://backend.s14-gap-b | grep title
<title>Welcome to nginx!</title>

$ kubectl -n s14-gap exec client -- wget -T 3 -q -O- http://backend.s14-gap-b.svc.cluster.local | grep title
<title>Welcome to nginx!</title>

$ kubectl -n s14-gap exec client -- nslookup backend.s14-gap-b.svc.cluster.local
Name:	backend.s14-gap-b.svc.cluster.local
Address: 10.96.112.195
```

One side note from the transcript: busybox's `nslookup backend.s14-gap-b`
(two labels, no search expansion) printed `NXDOMAIN`, while `wget` to the same
name worked, because `wget` uses the libc resolver, which applies the search
list. Test DNS with the tool the application actually uses, or with the full
FQDN.

### Issue E — pod networking: a NetworkPolicy silently drops traffic

**Identify.** [`05-netpol-app.yaml`](manifests/more-issues/05-netpol-app.yaml)
creates an `orders` pod. The pod is healthy, but requests to its IP hang:

```console
$ kubectl -n s14-gap exec client -- wget -T 3 -q -O- http://10.244.0.74; echo exit=$?
wget: download timed out
command terminated with exit code 1
exit=1
```

**Investigate.** Is the app at fault? Test it from inside its own network
namespace:

```console
$ kubectl -n s14-gap exec orders -- curl -s -o /dev/null -w 'from inside the pod: HTTP %{http_code}\n' http://localhost
from inside the pod: HTTP 200

$ kubectl -n s14-gap exec client -- ping -c 2 -W 2 10.244.0.74
2 packets transmitted, 0 packets received, 100% packet loss

$ kubectl -n s14-gap get networkpolicy
NAME                   POD-SELECTOR   AGE
default-deny-ingress   <none>         17s

$ kubectl -n s14-gap describe networkpolicy default-deny-ingress
Spec:
  PodSelector:     <none> (Allowing the specific traffic to all pods in this namespace)
  Allowing ingress traffic:
    <none> (Selected pods are isolated for ingress connectivity)
  Not affecting egress traffic
  Policy Types: Ingress
```

**Root cause.** The app answers on localhost, and even ICMP to the pod IP is
lost. Something between the pods is dropping packets, and a namespace-wide
`default-deny-ingress` policy is in place. A timeout (not "connection
refused") is what a NetworkPolicy drop looks like, because packets are
discarded with no reply. If the app were down or on the wrong port, the result
would be an immediate refusal. (kind's default CNI, kindnet, does enforce
NetworkPolicy. A CNI that doesn't would ignore the policy completely.)

**Fix and verify.** Leave the deny-all in place and add a narrow allow rule
([`05-FIXED-allow.yaml`](manifests/more-issues/05-FIXED-allow.yaml)): pods with
label `role=client` may reach `app=orders` on TCP 80.

```console
$ kubectl -n s14-gap get networkpolicy
NAME                     POD-SELECTOR   AGE
allow-client-to-orders   app=orders     10s
default-deny-ingress     <none>         27s

$ kubectl -n s14-gap exec client -- wget -T 3 -q -O- http://10.244.0.74 | grep title
<title>Welcome to nginx!</title>

$ kubectl -n s14-gap run intruder --image=busybox:1.36 --restart=Never --rm -i --quiet -- wget -T 3 -q -O- http://10.244.0.74; echo exit=$?
wget: download timed out
pod s14-gap/intruder terminated (Error)
exit=1
```

The labelled client now gets through. A pod without the label (`intruder`) is
still blocked, so this is a precise fix and not "turn the firewall off".

### Coverage of the spec's issue list

| Issue in the spec | Where |
|---|---|
| CrashLoopBackOff | Fault 2 |
| ImagePullBackOff | Fault 1, Issue A |
| ErrImagePull | Issue A (and the first status of Fault 1) |
| Pending | Fault 3 |
| ContainerCreating | Issue B |
| Service connectivity issues | Fault 5, mini project step 8 |
| DNS issues | Issue D (and Fault 5 step 1) |
| Pod networking issues | Issue E |
| Configuration issues | Issue C (and Fault 2's missing `DATABASE_URL`) |

---

## Task 3 — Mini project: the course troubleshooting challenge

The course mini project (`devops-heros/session-14-kubernetes-troubleshooting/mini-project/`)
was run on the original `devops-hw` cluster, using the files copied to
[`manifests/mini-project/`](manifests/mini-project/). The full real transcript is
[`evidence/session.txt`](evidence/session.txt). It was run in a namespace that
was then still called `assignment13`, from the old numbering. The course
folders `06-crashloopbackoff`, `07-imagepullbackoff` and `08-pending-pods` were
run in the same session ([`manifests/06-…`](manifests/06-crashloopbackoff/),
[`07-…`](manifests/07-imagepullbackoff/), [`08-…`](manifests/08-pending-pods/)).
The excerpts below come from that transcript, with the `--context` and
`-n assignment13` flags removed.

**Problem statement.** An nginx Deployment (2 replicas) sits behind
`troubleshooting-service`. The team reports that "something is wrong". Two
faults are introduced: a broken pod with a bad image, and a Service selector
changed to `app: wrong-app`.

### Steps 1–4 — deploy and check the healthy baseline

```console
$ kubectl apply -f manifests/mini-project/deployment.yaml -f manifests/mini-project/service.yaml -f manifests/client.yaml
deployment.apps/troubleshooting-app created
service/troubleshooting-service created
pod/client created

$ kubectl get pods,svc -o wide
NAME                                       READY   STATUS    RESTARTS   AGE   IP            NODE
pod/client                                 1/1     Running   0          27s   10.244.2.72   devops-hw-worker2
pod/troubleshooting-app-59d4957864-j744h   1/1     Running   0          27s   10.244.1.87   devops-hw-worker
pod/troubleshooting-app-59d4957864-kfz9q   1/1     Running   0          27s   10.244.2.71   devops-hw-worker2

NAME                              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE   SELECTOR
service/troubleshooting-service   ClusterIP   10.96.235.104   <none>        80/TCP    27s   app=troubleshooting-app

$ kubectl exec deploy/troubleshooting-app -- curl -s -o /dev/null -w "HTTP %{http_code}\n" localhost
HTTP 200

$ kubectl logs deploy/troubleshooting-app --tail=8
Found 2 pods, using pod/troubleshooting-app-59d4957864-kfz9q
2026/09/21 09:43:02 [notice] 1#1: start worker process 47
127.0.0.1 - - [21/Sep/2026:09:43:05 +0000] "GET / HTTP/1.1" 200 615 "-" "curl/7.88.1" "-"
```

The `curl localhost` from `exec` shows up in the nginx access log on the next
line, so the app is healthy before anything is broken.

### Steps 5–7 — the broken pod

```console
$ kubectl apply -f manifests/mini-project/broken-pod.yaml
pod/project-broken-pod created

(status sampled repeatedly)  ContainerCreating -> ContainerCreating -> ErrImagePull x6 -> ImagePullBackOff

$ kubectl get pod project-broken-pod -o wide
NAME                 READY   STATUS             RESTARTS   AGE   IP            NODE
project-broken-pod   0/1     ImagePullBackOff   0          16s   10.244.1.94   devops-hw-worker

$ kubectl describe pod project-broken-pod
    Image:          nginx:this-tag-does-not-exist
    State:          Waiting
      Reason:       ImagePullBackOff
Events:
  Normal   Scheduled  16s   default-scheduler  Successfully assigned assignment13/project-broken-pod to devops-hw-worker
  Warning  Failed     14s   kubelet            spec.containers{app}: Failed to pull image "nginx:this-tag-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": docker.io/library/nginx:this-tag-does-not-exist: not found
  Warning  Failed     14s   kubelet            spec.containers{app}: Error: ErrImagePull
  Normal   BackOff    14s   kubelet            spec.containers{app}: Back-off pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     14s   kubelet            spec.containers{app}: Error: ImagePullBackOff

$ kubectl delete pod project-broken-pod --wait=true
$ kubectl apply -f manifests/mini-project/fixed-pod.yaml
$ kubectl get pod project-broken-pod
NAME                 READY   STATUS    RESTARTS   AGE
project-broken-pod   1/1     Running   0          1s
```

**The five questions from step 7:**

| # | Question | Answer |
|---|---|---|
| 1 | What is the Pod status? | `ImagePullBackOff` (after `ContainerCreating` and several `ErrImagePull`). Phase `Pending`, `0/1`, 0 restarts |
| 2 | What is the actual error? | `failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": … not found` (`code = NotFound`) |
| 3 | Which command found the reason? | `kubectl describe pod project-broken-pod`, in the **Events** section. `kubectl logs` can't help because the container never started |
| 4 | What is wrong with the image? | The tag `this-tag-does-not-exist` does not exist in the `nginx` repository on Docker Hub. The registry and repository are fine; the tag is not |
| 5 | How would you fix it? | Use a real tag (`nginx:1.27` in [`fixed-pod.yaml`](manifests/mini-project/fixed-pod.yaml)) and recreate the pod, because a pod's image can't be changed in place. In a Deployment, `kubectl set image` triggers a rollout |

### Steps 8–9 — the Service selector challenge

```console
$ kubectl apply -f manifests/mini-project/broken-service.yaml        # selector: app: wrong-app
service/troubleshooting-service configured

$ kubectl exec client -- wget -T 3 -q -O- http://troubleshooting-service
wget: can't connect to remote host (10.96.235.104): Connection refused
command terminated with exit code 1

$ kubectl exec client -- nslookup troubleshooting-service.assignment13.svc.cluster.local
Name:	troubleshooting-service.assignment13.svc.cluster.local
Address: 10.96.235.104

$ kubectl describe svc troubleshooting-service
Selector:                 app=wrong-app
TargetPort:               80/TCP
Endpoints:                

$ kubectl get endpointslices -l kubernetes.io/service-name=troubleshooting-service -o yaml
  endpoints: null

$ kubectl get pods --show-labels
NAME                                   READY   STATUS    RESTARTS   AGE     LABELS
troubleshooting-app-59d4957864-j744h   1/1     Running   0          3m36s   app=troubleshooting-app,pod-template-hash=59d4957864
troubleshooting-app-59d4957864-kfz9q   1/1     Running   0          3m36s   app=troubleshooting-app,pod-template-hash=59d4957864
```

DNS resolves the name to the ClusterIP, so DNS is fine. The connection is
refused because the Service has no endpoints. The selector says
`app=wrong-app` and the pods are labelled `app=troubleshooting-app`.

```console
$ kubectl apply -f manifests/mini-project/service.yaml               # selector restored
service/troubleshooting-service configured

$ kubectl get endpointslices -l kubernetes.io/service-name=troubleshooting-service
NAME                            ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
troubleshooting-service-8wqx9   IPv4          80      10.244.1.87,10.244.2.71   3m40s

$ kubectl exec client -- wget -T 5 -q -O- http://troubleshooting-service
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
...
```

After the fix the endpoint IPs are exactly the two pod IPs from step 1, and the
Service returns the nginx page.

### Step 10 — final checklist, and step 11 — troubleshooting table

The step-10 commands (`get pods`, `describe pod`, `logs`, `exec`, `get events`,
`describe service`, `get endpoints`, `nslookup`) are all in the transcript
above, and `kubectl events` is used in Task 1.

| Problem | What I saw | Command I used | Root cause | Fix |
| :--- | :--- | :--- | :--- | :--- |
| **Broken Pod** | `0/1`, `ContainerCreating` → `ErrImagePull` → `ImagePullBackOff`, 0 restarts | `kubectl get pod`, `kubectl describe pod` (Events) | container never started, because its image could not be pulled | recreate with a valid image (`fixed-pod.yaml`) |
| **Service Problem** | DNS resolves, but `Connection refused`; `Endpoints:` empty | `kubectl describe svc`, `kubectl get endpointslices`, `kubectl get pods --show-labels` | selector `app=wrong-app` matches no pod labels | restore selector `app=troubleshooting-app` (`service.yaml`) |
| **Image Problem** | `Failed to pull image "nginx:this-tag-does-not-exist" … not found` | `kubectl describe pod`, `kubectl get events --field-selector type=Warning` | tag does not exist in the registry (`NotFound`, not auth or network) | use an existing tag, `nginx:1.27` |

### Step 12 — README questions

1. **What does `kubectl get` tell us?** The current state of a resource in
   one line: status, ready count, restarts, age, and with `-o wide` the IP and
   node. It tells you *what* is wrong and which direction to look.
2. **`get` vs `describe`?** `get` is a summary from the object's status.
   `describe` adds the full spec, the conditions, and the **Events** recorded
   by the scheduler and kubelet. Those events usually explain *why*.
3. **Why `kubectl logs`?** To see what the application printed (stdout/stderr).
   It is the tool for problems *inside* a container that started, like a crash
   loop. Use `--previous` for the container that just died.
4. **When `kubectl exec`?** When the container is running and you need to
   check what is really inside: `curl localhost`, env vars, mounted files,
   resolv.conf, connectivity to other pods.
5. **`CrashLoopBackOff`?** The container starts and keeps exiting, and the
   kubelet waits longer and longer before each restart. The cause is in the
   app's logs (see Fault 2).
6. **`ImagePullBackOff`?** The image could not be pulled (wrong tag, wrong
   registry, no auth, no network), and the kubelet is backing off between
   retries. `ErrImagePull` is the first failure. The container never started,
   so there are no logs.
7. **Why can a Pod stay `Pending`?** Nothing could schedule it: not enough CPU
   or memory, nodeSelector/affinity doesn't match, an untolerated taint, or an
   unbound PVC. `describe` shows a `FailedScheduling` event with the per-node
   reasons (Fault 3).
8. **Why can a Service have no endpoints?** Its selector matches no pods
   (typo, label mismatch), the matching pods are not Ready, or there are none
   at all.
9. **Selector and labels?** A Service sends traffic to every *Ready* pod whose
   labels include all the selector's key/value pairs. The EndpointSlice
   controller keeps that list updated as pods come and go. A single mismatched
   character means zero endpoints.
10. **What is Kubernetes DNS?** CoreDNS, running in `kube-system` behind the
    `kube-dns` Service (`10.96.0.10`). Every pod's `/etc/resolv.conf` points at
    it, and it resolves `<service>.<namespace>.svc.cluster.local` to the
    Service's ClusterIP (Issue D, and session 11).

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
| 1 | `kubectl events`, `kubectl explain`, `kubectl top`, `get -o wide` | Done — [Task 1, completed](#task-1-completed--kubectl-events-kubectl-explain-kubectl-top-get--o-wide) |
| 2 | `ErrImagePull` (unresolvable registry) | Done — Issue A, fixed and verified |
| 2 | `ContainerCreating` (missing ConfigMap volume) | Done — Issue B, recovered without recreating the pod |
| 2 | Configuration issue (`CreateContainerConfigError`) | Done — Issue C, wrong Secret key |
| 2 | DNS issue (cross-namespace short name) | Done — Issue D, NXDOMAIN on own-namespace search path |
| 2 | Pod networking issue (NetworkPolicy) | Done — Issue E, timeout diagnosed, narrow allow rule, intruder still blocked |
| 3 | Mini project | Done — [Task 3](#task-3--mini-project-the-course-troubleshooting-challenge): broken pod + selector challenge, 5 questions, table, 10 README questions |
