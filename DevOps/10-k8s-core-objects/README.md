# Kubernetes Core Objects — Homework

Session 10. Pod lifecycle, the controller objects (ReplicaSet, Deployment,
DaemonSet, StatefulSet), and the four deployment strategies — with the
strategies **measured under continuous HTTP load** rather than described.

Command results are **real captured output** from the three-node kind cluster
built in [session 09](../09-kubernetes-fundamentals/README.md).

---

## Task 1 — Pod lifecycle: all five phases, reproduced on purpose

A Pod's `status.phase` is only ever one of five values. Rather than read that in
a table, each one was deliberately provoked. All seven manifests are in
[`manifests/lifecycle/`](manifests/lifecycle/) and were applied at once:

```bash
$ kubectl apply -f manifests/lifecycle/
pod/phase-succeeded created
pod/phase-failed created
pod/phase-pending created
pod/phase-crashloop created
pod/phase-imagepull created
pod/init-demo created
pod/sidecar-demo created
```

75 seconds later:

```bash
$ kubectl get pods -o wide
NAME              READY   STATUS         RESTARTS      AGE   IP            NODE                NOMINATED NODE   READINESS GATES
init-demo         1/1     Running        0             75s   10.244.1.11   devops-hw-worker    <none>           <none>
phase-crashloop   0/1     Error          3 (51s ago)   75s   10.244.1.10   devops-hw-worker    <none>           <none>
phase-failed      0/1     Error          0             75s   10.244.2.7    devops-hw-worker2   <none>           <none>
phase-imagepull   0/1     ErrImagePull   0             75s   10.244.2.8    devops-hw-worker2   <none>           <none>
phase-pending     0/1     Pending        0             75s   <none>        <none>              <none>           <none>
phase-succeeded   0/1     Completed      0             75s   10.244.1.9    devops-hw-worker    <none>           <none>
sidecar-demo      2/2     Running        0             75s   10.244.2.9    devops-hw-worker2   <none>           <none>
```

### STATUS is not the same thing as phase

The `STATUS` column is a friendly summary that `kubectl` synthesises. The actual
API field is `status.phase`, and the two disagree often enough to matter:

```bash
$ kubectl get pods -o custom-columns='NAME:.metadata.name,PHASE:.status.phase,REASON:.status.containerStatuses[0].state.waiting.reason,EXIT:.status.containerStatuses[0].state.terminated.exitCode,RESTARTS:.status.containerStatuses[0].restartCount'
NAME              PHASE       REASON         EXIT     RESTARTS
init-demo         Running     <none>         <none>   0
phase-crashloop   Running     <none>         1        3
phase-failed      Failed      <none>         7        0
phase-imagepull   Pending     ErrImagePull   <none>   0
phase-pending     Pending     <none>         <none>   <none>
phase-succeeded   Succeeded   <none>         0        0
sidecar-demo      Running     <none>         <none>   0
```

Read that carefully — two rows are genuinely surprising:

- **`phase-crashloop` has phase `Running`.** A pod stuck in a crash loop is *not*
  in a failed phase. Its `restartPolicy` is `Always`, so Kubernetes considers it
  an ongoing, healthy-in-principle workload that simply keeps dying. Any alert
  written as "phase != Running" will miss a crash-looping pod entirely.
- **`phase-imagepull` has phase `Pending`.** An image that cannot be pulled is a
  *Pending* pod, not a failed one, because the container was never created.

| Phase | Provoked by | Seen as |
|---|---|---|
| `Succeeded` | container exits 0, `restartPolicy: Never` | `Completed` |
| `Failed` | container exits 7, `restartPolicy: Never` | `Error` |
| `Pending` | resource request no node can satisfy | `Pending` |
| `Pending` | image tag does not exist | `ErrImagePull` → `ImagePullBackOff` |
| `Running` | container exits 1 repeatedly, `restartPolicy: Always` | `Error` ↔ `CrashLoopBackOff` |

### Pending — the scheduler explains itself

```yaml
resources:
  requests:
    cpu: "500"          # 500 whole cores
    memory: 2000Gi
```

```bash
$ kubectl describe pod phase-pending | sed -n '/^Events:/,$p'
Events:
  Type     Reason            Age                   From               Message
  ----     ------            ----                  ----               -------
  Warning  FailedScheduling  2m8s (x3 over 2m14s)  default-scheduler  0/3 nodes are available: 1 node(s) had untolerated taint(s), 2 Insufficient cpu, 2 Insufficient memory. preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling.
```

That one line accounts for all three nodes separately: **1** rejected on a taint
(the control plane), **2** rejected on capacity. The scheduler always tells you
exactly why, per node, and `preemption: … not helpful` means evicting
lower-priority pods would not create room either.

### Failed — the exit code survives the container

```bash
$ kubectl logs phase-failed
about to fail

$ kubectl get pod phase-failed -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode} {.status.containerStatuses[0].state.terminated.reason}'; echo
7 Error
```

Exit code **7**, exactly as the manifest specified. Logs and exit status remain
readable after the container is dead, which is what makes post-mortem debugging
possible at all.

### CrashLoopBackOff — catching the status flip

`CrashLoopBackOff` is not a phase, it is a *waiting reason*, and the pod only
wears it during the back-off sleep between restarts. While the container is
briefly running-then-dying, the STATUS reads `Error` instead. Sampling every
3 seconds caught the exact moment it flips:

```
08:42:59  phase-crashloop   0/1   Error              5 (2m23s ago)   4m
08:43:02  phase-crashloop   0/1   Error              5 (2m26s ago)   4m3s
08:43:05  phase-crashloop   0/1   Error              5 (2m29s ago)   4m6s
08:43:08  phase-crashloop   0/1   CrashLoopBackOff   5 (65s ago)     4m9s
08:43:11  phase-crashloop   0/1   CrashLoopBackOff   5 (68s ago)     4m12s
08:43:14  phase-crashloop   0/1   CrashLoopBackOff   5 (71s ago)     4m15s
```

The back-off is exponential — 10s, 20s, 40s, 80s, capped at 5 minutes — which is
why a crash-looping pod gets *slower* to retry the longer it is broken, and why
a pod that has been failing for an hour can sit apparently idle for minutes at a
time.

The application's own last words are still available:

```bash
$ kubectl logs phase-crashloop
starting up
fatal: cannot reach database
```

And the kubelet records the back-off explicitly:

```bash
$ kubectl describe pod phase-crashloop | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  3m11s              default-scheduler  Successfully assigned default/phase-crashloop to devops-hw-worker
  Normal   Pulling    3m11s              kubelet            spec.containers{crasher}: Pulling image "busybox:1.36"
  Normal   Pulled     3m5s               kubelet            spec.containers{crasher}: Successfully pulled image "busybox:1.36" in 1.317s (5.957s including waiting). Image size: 1906887 bytes.
  Normal   Created    9s (x6 over 3m5s)  kubelet            spec.containers{crasher}: Container created
  Normal   Started    9s (x6 over 3m5s)  kubelet            spec.containers{crasher}: Container started
  Normal   Pulled     9s (x5 over 3m3s)  kubelet            spec.containers{crasher}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Warning  BackOff    7s (x5 over 3m)    kubelet            spec.containers{crasher}: Back-off restarting failed container crasher in pod phase-crashloop_default(fdbca7e9-8d91-4a5f-9ab3-e3bcd4650776)
```

`Created (x6)` and `Started (x6)` — six attempts, all recorded on one event line
with a repeat count, which is why event lists stay short even for pods that have
been failing for hours.

### ImagePullBackOff

```bash
$ kubectl describe pod phase-imagepull | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m14s                default-scheduler  Successfully assigned default/phase-imagepull to devops-hw-worker2
  Normal   Pulling    31s (x4 over 2m14s)  kubelet            spec.containers{app}: Pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     26s (x4 over 2m8s)   kubelet            spec.containers{app}: Failed to pull image "nginx:this-tag-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": docker.io/library/nginx:this-tag-does-not-exist: not found
  Warning  Failed     26s (x4 over 2m8s)   kubelet            spec.containers{app}: Error: ErrImagePull
  Normal   BackOff    3s (x7 over 2m8s)    kubelet            spec.containers{app}: Back-off pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     3s (x7 over 2m8s)    kubelet            spec.containers{app}: Error: ImagePullBackOff
```

The distinction worth knowing for interviews: **`ErrImagePull` is the first
failure, `ImagePullBackOff` is the state it settles into** once the kubelet
starts rate-limiting its retries. The underlying `rpc error … NotFound` names
the real cause — here a bad tag. A **private registry with no `imagePullSecret`**
produces the same two states but with `401 Unauthorized` in that line instead,
which is how you tell the two apart.

### Init containers — run to completion, in order, before anything else

[`manifests/lifecycle/06-init-container.yaml`](manifests/lifecycle/06-init-container.yaml)
has an init container that writes into a shared `emptyDir` and exits; the main
nginx then serves what it wrote.

```bash
$ kubectl logs init-demo -c wait-for-config
init: preparing shared volume
init: done

$ kubectl exec init-demo -c web -- cat /usr/share/nginx/html/index.html
generated by init container

$ kubectl get pod init-demo -o jsonpath='{range .status.initContainerStatuses[*]}{.name}: {.state}{"\n"}{end}'
wait-for-config: {"terminated":{"containerID":"containerd://5bc7e58257dbc8ade0b492108b130dfeea1740a86282df3178fa7182ab405a97","exitCode":0,"finishedAt":"2026-09-21T08:39:12Z","reason":"Completed","startedAt":"2026-09-21T08:39:07Z"}}
```

The init container is `terminated / Completed` while the pod is `Running`. It
ran for 5 seconds, and nginx did not start until it was done — that ordering
guarantee is the whole point (waiting for a database, fetching config, running
migrations).

### Multi-container pods — the sidecar pattern

Two containers, one `emptyDir`, one writer and one reader:

```bash
$ kubectl get pod sidecar-demo -o jsonpath='{range .spec.containers[*]}{.name} {end}'; echo
web content-sidecar

$ kubectl exec sidecar-demo -c web -- cat /usr/share/nginx/html/index.html
sidecar write #26 at 08:41:12

$ sleep 6; kubectl exec sidecar-demo -c web -- cat /usr/share/nginx/html/index.html
sidecar write #27 at 08:41:17
```

Write #26 became #27 without anything restarting. The sidecar is updating a
volume that the web container is serving from, live — the two containers share a
filesystem and a network namespace, which is the entire reason a Pod is a group
of containers rather than a single one. `-c` is mandatory once a pod has more
than one container.

### The rest of the course lifecycle lab: Running, readiness, liveness, startup, graceful termination

The spec says *"for each YAML file"*. The course lab
(`devops-heros/session10-k8s-core-objects/pod-lifecycle/`) has twelve files and
the seven above cover seven of them. The other five are copied unchanged as
[`08-running.yaml`](manifests/lifecycle/08-running.yaml),
[`09-readiness.yaml`](manifests/lifecycle/09-readiness.yaml),
[`10-liveness.yaml`](manifests/lifecycle/10-liveness.yaml),
[`11-startup.yaml`](manifests/lifecycle/11-startup.yaml) and
[`12-termination.yaml`](manifests/lifecycle/12-termination.yaml). Each one was
applied, its status and details checked, and the output captured on a
single-node kind cluster (`hw-legacy`, images pre-pulled so the timings show
the probes and not the image downloads). Full transcript:
[`evidence/s10-lifecycle-course-labs.txt`](evidence/s10-lifecycle-course-labs.txt).
Watch timestamps are local time (IST); event timestamps are UTC (5h30m behind).

#### 08 — Running (the normal case)

```console
$ kubectl apply -f manifests/lifecycle/08-running.yaml
pod/lifecycle-running created

$ kubectl get pod lifecycle-running -o wide
NAME                READY   STATUS    RESTARTS   AGE   IP            NODE                      NOMINATED NODE   READINESS GATES
lifecycle-running   1/1     Running   0          1s    10.244.0.10   hw-legacy-control-plane   <none>           <none>

$ kubectl get pod lifecycle-running -o jsonpath='{.status.phase}{"  "}{.status.containerStatuses[0].state}{"\n"}'
Running  {"running":{"startedAt":"2026-10-07T13:19:41Z"}}

$ kubectl describe pod lifecycle-running | sed -n '/^Conditions:/,/^Volumes:/p;/^Events:/,$p'
Conditions:
  Type                        Status
  PodReadyToStartContainers   True 
  Initialized                 True 
  Ready                       True 
  ContainersReady             True 
  PodScheduled                True 
Events:
  Normal  Scheduled  1s    default-scheduler  Successfully assigned s10-lifecycle/lifecycle-running to hw-legacy-control-plane
  Normal  Pulled     1s    kubelet            spec.containers{nginx}: Container image "nginx:1.27" already present on machine ...
  Normal  Created    1s    kubelet            spec.containers{nginx}: Container created
  Normal  Started    0s    kubelet            spec.containers{nginx}: Container started
```

**Observed:** phase `Running`, container state `running`, and all five pod
conditions `True`. The conditions are checked in order (`PodScheduled`, then
`Initialized`, then `ContainersReady`, then `Ready`), and the four events show
who did each step: the scheduler picked the node, then the kubelet did the rest.

#### 09 — Readiness probe: Running is not the same as Ready

```console
$ kubectl apply -f manifests/lifecycle/09-readiness.yaml
pod/lifecycle-readiness created

[18:49:41]  lifecycle-readiness   0/1     ContainerCreating   0          0s
[18:49:44]  lifecycle-readiness   0/1     Running             0          3s
[18:49:47]  lifecycle-readiness   1/1     Running             0          6s

$ kubectl get pod lifecycle-readiness -o jsonpath='{range .status.conditions[*]}{.type}{"="}{.status}{"  at "}{.lastTransitionTime}{"\n"}{end}'
PodReadyToStartContainers=True  at 2026-10-07T13:19:41Z
Initialized=True  at 2026-10-07T13:19:41Z
Ready=True  at 2026-10-07T13:19:47Z
ContainersReady=True  at 2026-10-07T13:19:47Z
PodScheduled=True  at 2026-10-07T13:19:41Z

$ kubectl describe pod lifecycle-readiness | grep Readiness:
    Readiness:      http-get http://:80/ delay=5s timeout=1s period=5s successThreshold=1 failureThreshold=3
```

**Observed:** for about 6 seconds the pod was `Running` but `0/1`. The container
was up, but `initialDelaySeconds: 5` meant the first `GET /` had not happened
yet. `Ready` flipped at 13:19:47, six seconds after the other conditions. A
Service only sends traffic to pods that are `Ready`, so this probe decides when
traffic arrives. It never restarts anything.

#### 10 — Liveness probe: the kubelet restarts the container

The container creates `/tmp/healthy`, deletes it after 20 s, then keeps
running. The probe checks for the file every 5 s with `failureThreshold: 2`.

```console
$ kubectl get pod lifecycle-liveness -w
[18:52:07] lifecycle-liveness   0/1     ContainerCreating   0          0s
[18:52:08] lifecycle-liveness   1/1     Running             0          1s
[18:53:08] lifecycle-liveness   1/1     Running             1 (1s ago)   61s

$ kubectl get events --field-selector involvedObject.name=lifecycle-liveness ...   (second run)
FIRST                  LAST                   COUNT   REASON      MESSAGE
2026-10-07T13:22:08Z   2026-10-07T13:23:08Z   2       Started     Container started
2026-10-07T13:22:32Z   2026-10-07T13:23:37Z   4       Unhealthy   Liveness probe failed: 
2026-10-07T13:22:37Z   2026-10-07T13:23:37Z   2       Killing     Container app failed liveness probe, will be restarted

$ kubectl describe pod lifecycle-liveness      (from the first run)
    Last State:     Terminated
      Reason:       Error
      Exit Code:    137
      Started:      Wed, 07 Oct 2026 18:50:04 +0530
      Finished:     Wed, 07 Oct 2026 18:51:04 +0530
    Restart Count:  1
    Liveness:       exec [sh -c test -f /tmp/healthy] delay=5s timeout=1s period=5s successThreshold=1 failureThreshold=2

$ kubectl logs lifecycle-liveness --previous
App started
Health file removed
```

**Observed:** first failure at +24 s (the file was gone at +20 s), second at
+29 s, and `Killing … will be restarted` at that point. The restart only
appears at **+60 s**. I did not expect that gap. The container's PID 1 is
`sh`, which ignores SIGTERM, so the kubelet waited out the default 30 s grace
period and then sent SIGKILL. That is why the exit code is **137** (128 + 9) and
not a clean 0. `--previous` shows the logs of the container that was killed. A
liveness restart keeps the same pod (same name, same IP) and only increments
`RESTARTS`.

#### 11 — Startup probe: protecting a slow starter

The app sleeps 30 s before creating `/tmp/started`. The startup probe allows
`10 × 5 s = 50 s`.

```console
$ kubectl get pod lifecycle-startup -w
[18:52:07] lifecycle-startup   0/1     ContainerCreating   0          0s
[18:52:08] lifecycle-startup   0/1     Running             0          1s
[18:52:42] lifecycle-startup   1/1     Running             0          35s

$ kubectl get events --field-selector involvedObject.name=lifecycle-startup ...   (second run)
2026-10-07T13:22:08Z   2026-10-07T13:22:08Z   1       Started     Container started
2026-10-07T13:22:12Z   2026-10-07T13:22:37Z   6       Unhealthy   Startup probe failed: 

$ kubectl get pod lifecycle-startup -o jsonpath='started={...started} ready={...ready} restarts={...restartCount}'
started=true ready=true restarts=0

$ kubectl logs lifecycle-startup
Application starting...
Application started
```

**Observed:** six startup-probe failures in a row, logged as `Warning
Unhealthy`, and **zero restarts**. Startup-probe failures only count against
the `failureThreshold` budget. They do not kill anything until that budget runs
out. The probe passed at +35 s and the pod became `1/1`. With a 10 s budget
instead of 50 s, this container would have been killed before it finished
starting. Session 13 runs that experiment.

#### 12 — Graceful termination: SIGTERM, cleanup, then exit

The script traps `TERM`, spends 10 s "cleaning up", then exits 0.
`terminationGracePeriodSeconds: 20`.

```console
$ kubectl get pod lifecycle-termination -o jsonpath='terminationGracePeriodSeconds={.spec.terminationGracePeriodSeconds}'
terminationGracePeriodSeconds=20

[18:53:55] $ time kubectl delete pod lifecycle-termination
pod "lifecycle-termination" deleted from s10-lifecycle namespace
[18:54:05] delete returned after 10 seconds

$ kubectl logs -f lifecycle-termination      (second terminal)
[18:53:53] Application running
[18:53:55] SIGTERM received; cleaning up...
[18:54:05] Cleanup complete

$ kubectl get pod lifecycle-termination -w   (third terminal)
[18:53:53] lifecycle-termination   1/1     Running       0          1s
[18:53:55] lifecycle-termination   1/1     Terminating   0          3s
[18:54:05] lifecycle-termination   0/1     Completed     0          13s
```

**Observed:** the delete sent SIGTERM straight away. The pod went
`Terminating` and the app logged the trap. Exactly 10 s later the cleanup
finished, the process exited 0 (`Completed`, not `Error`) and the delete
returned. That was well within the 20 s grace period, so no SIGKILL was needed.
Compare this with the liveness pod above: there PID 1 ignored SIGTERM, used the
full 30 s and was killed with exit 137. Handling SIGTERM is what makes rolling
updates drain cleanly instead of cutting off requests.

#### All twelve lifecycle files

| File | Status seen | Phase | What it demonstrates |
|---|---|---|---|
| 01-succeeded | `Completed` | Succeeded | exit 0, `restartPolicy: Never` |
| 02-failed | `Error` | Failed | exit 7, `restartPolicy: Never` |
| 03-pending | `Pending` | Pending | unsatisfiable resource request |
| 04-crashloop | `Error` ↔ `CrashLoopBackOff` | Running | repeated exit 1 with back-off |
| 05-imagepull | `ErrImagePull` → `ImagePullBackOff` | Pending | image tag does not exist |
| 06-init-container | `1/1 Running`, init container `Completed` | Running | init runs to completion first |
| 07-multi-container | `2/2 Running` | Running | sidecar sharing an `emptyDir` |
| 08-running | `1/1 Running` | Running | all conditions True |
| 09-readiness | `0/1 Running` → `1/1` | Running | Ready lags Running by the probe delay |
| 10-liveness | `RESTARTS 1` | Running | failed probe → kill (137) → restart |
| 11-startup | `0/1` for 35 s, 0 restarts | Running | slow start protected |
| 12-termination | `Terminating` → `Completed`, then removed | (deleted) | SIGTERM trap, 10 s cleanup within 20 s grace |

---

## Task 2 — ReplicaSet: ownership is by label, not by name

[`manifests/core-objects/replicaset.yaml`](manifests/core-objects/replicaset.yaml)

```bash
$ kubectl apply -f manifests/core-objects/replicaset.yaml
replicaset.apps/backend-rs created

$ kubectl get rs backend-rs -o wide
NAME         DESIRED   CURRENT   READY   AGE   CONTAINERS   IMAGES              SELECTOR
backend-rs   3         3         3       12s   backend      nginx:1.27-alpine   app=backend

$ kubectl get pods -l app=backend -o jsonpath='{range .items[*]}{.metadata.name}{"  owner="}{.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}{end}'
backend-rs-2l454  owner=ReplicaSet/backend-rs
backend-rs-mrcxk  owner=ReplicaSet/backend-rs
backend-rs-nxxmh  owner=ReplicaSet/backend-rs
```

`ownerReferences` is what makes garbage collection work: delete the ReplicaSet
and the pods go with it, because each pod carries a pointer back to its owner.

### The adoption experiment

A ReplicaSet does not track "the pods I created". It counts **pods matching its
selector**, and it will take ownership of any pod wearing the right label. To
prove it, a completely unrelated bare pod was created with `app=backend`:

```bash
$ kubectl run orphan-pod --image=nginx:1.27-alpine --labels='app=backend'
pod/orphan-pod created
```

Sampling every second immediately afterwards:

```
08:45:02  backend-rs-8whqt   1/1   Running       0     1s|backend-rs-hsn8q   1/1   Running       0     1s|backend-rs-wpbh4   1/1   Running       0     1s|orphan-pod         0/1   Terminating   0     0s|
08:45:03  backend-rs-8whqt   1/1   Running       0     2s|backend-rs-hsn8q   1/1   Running       0     2s|backend-rs-wpbh4   1/1   Running       0     2s|orphan-pod         0/1   Terminating   0     1s|
08:45:04  backend-rs-8whqt   1/1   Running   0     3s|backend-rs-hsn8q   1/1   Running   0     3s|backend-rs-wpbh4   1/1   Running   0     3s|
```

`orphan-pod` was `Terminating` **within one second of being created**. The
ReplicaSet counted 4 pods matching `app=backend`, wanted 3, and killed one. And
it says so itself:

```bash
$ kubectl describe rs backend-rs | sed -n '/^Events:/,$p'
Events:
  Type    Reason            Age   From                   Message
  ----    ------            ----  ----                   -------
  Normal  SuccessfulCreate  14s   replicaset-controller  Created pod: backend-rs-8whqt
  Normal  SuccessfulCreate  14s   replicaset-controller  Created pod: backend-rs-hsn8q
  Normal  SuccessfulCreate  14s   replicaset-controller  Created pod: backend-rs-wpbh4
  Normal  SuccessfulDelete  13s   replicaset-controller  Deleted pod: orphan-pod
```

```bash
$ kubectl get pod orphan-pod
Error from server (NotFound): pods "orphan-pod" not found
```

**`SuccessfulDelete … Deleted pod: orphan-pod`** — a controller destroyed a pod
it had never created, purely because a label matched. This is the single most
important thing to understand about Kubernetes controllers, and it is why
overlapping selectors between two Deployments is such a damaging mistake: they
will fight over each other's pods forever.

---

## Task 3 — Deployment: rollout, history, rollback

A Deployment does not manage pods. It manages **ReplicaSets**, one per version
of the pod template.

```bash
$ kubectl get rs -l app=app-rolling
NAME                    DESIRED   CURRENT   READY   AGE
app-rolling-c6b94689b   4         4         4       18s
```

After applying v2:

```bash
$ kubectl get rs -l app=app-rolling
NAME                     DESIRED   CURRENT   READY   AGE
app-rolling-846f554989   4         4         4       24s
app-rolling-c6b94689b    0         0         0       42s
```

The old ReplicaSet is **kept at 0 replicas, not deleted**. That retained object
*is* the rollback mechanism — undoing a release is just scaling the old
ReplicaSet back up and the new one down.

```bash
$ kubectl rollout history deploy/app-rolling
deployment.apps/app-rolling
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
```

### Rolling back

```bash
$ kubectl exec deploy/app-rolling -- cat /usr/share/nginx/html/index.html
VERSION v2 | pod app-rolling-846f554989-pv4tn

$ kubectl get deploy app-rolling -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
nginx:1.27-alpine

$ kubectl rollout undo deploy/app-rolling
Warning: resource deployments/app-rolling was previously managed with 'kubectl apply'. Rolling back will not update the kubectl.kubernetes.io/last-applied-configuration annotation, which may cause unexpected behavior on future 'kubectl apply' operations. Consider using 'kubectl apply' with your previous configuration file instead.
deployment.apps/app-rolling rolled back

$ kubectl exec deploy/app-rolling -- cat /usr/share/nginx/html/index.html
VERSION v1 | pod app-rolling-c6b94689b-fl5l9

$ kubectl get deploy app-rolling -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
nginx:1.26-alpine
```

That warning is worth reading rather than ignoring. `rollout undo` changes the
live object but **not** the `last-applied-configuration` annotation, so the next
`kubectl apply` of the unchanged v2 file would silently push v2 straight back
out. In a GitOps setup this is exactly how a "rolled back" incident re-breaks
itself minutes later. The safe rollback is to commit and apply the old manifest.

Note also what happened to the revision numbers:

```bash
$ kubectl rollout history deploy/app-rolling
deployment.apps/app-rolling
REVISION  CHANGE-CAUSE
2         <none>
3         <none>
```

Revision 1 is **gone** and a new revision 3 appeared. Rolling back does not
rewind history, it appends to it — the old template is replayed as a new
revision.

```bash
$ kubectl get rs -l app=app-rolling
NAME                     DESIRED   CURRENT   READY   AGE
app-rolling-846f554989   0         0         0       56s
app-rolling-c6b94689b    4         4         4       74s
```

The same two ReplicaSets, with their replica counts swapped. No new pods
template was ever created.

---

## Task 4 — The four deployment strategies, measured

Rather than assert which strategies cause downtime, each rollout was performed
while a loop hammered the Service continuously, recording **curl's exit code for
every single request**. The poller sends one request per iteration and logs the
result with millisecond timestamps.

### Establishing a baseline first

Any measurement is worthless without knowing the noise floor, so the same poller
was first run for 20 seconds against a steady, untouched deployment:

```
requests = 1596
failed   = 0
```

**Zero failures in 1596 requests with nothing changing.** Anything the rollouts
produce is therefore real, not measurement noise.

### Results

| Strategy | Requests | Failed | Failure pattern |
|---|---|---|---|
| Baseline (no rollout) | 1596 | **0** | — |
| **RollingUpdate** (`maxSurge:1, maxUnavailable:0`) | 631 | 5 | isolated single requests, scattered |
| **RollingUpdate + `preStop`** | 517 | 4 | isolated single requests, scattered |
| **Recreate** | 192 | 7 | **one contiguous outage** |
| **Blue-Green** | 1019 | **0** | none |
| **Canary** (9:1) | 1026 | **0** | none |

### Strategy 1 — RollingUpdate

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1          # at most 1 pod above desired
    maxUnavailable: 0    # never drop below desired ready count
```

Sampling pod-by-pod state every second during the v1→v2 rollout of 4 replicas:

```
08:45:57  app-rolling-846f554989-pv4tn(v2,ready=false) app-rolling-c6b94689b-ffjmg(v1,ready=true) app-rolling-c6b94689b-mmtzg(v1,ready=true) app-rolling-c6b94689b-q4b8l(v1,ready=true) app-rolling-c6b94689b-tmplb(v1,ready=true)
08:46:01  app-rolling-846f554989-95pg5(v2,ready=false) app-rolling-846f554989-pv4tn(v2,ready=true) app-rolling-c6b94689b-ffjmg(v1,ready=true) app-rolling-c6b94689b-mmtzg(v1,ready=false) app-rolling-c6b94689b-q4b8l(v1,ready=true) app-rolling-c6b94689b-tmplb(v1,ready=true)
08:46:04  app-rolling-846f554989-4f8lt(v2,ready=false) app-rolling-846f554989-95pg5(v2,ready=true) app-rolling-846f554989-pv4tn(v2,ready=true) app-rolling-c6b94689b-ffjmg(v1,ready=true) app-rolling-c6b94689b-q4b8l(v1,ready=false) app-rolling-c6b94689b-tmplb(v1,ready=true)
08:46:07  app-rolling-846f554989-4f8lt(v2,ready=true) app-rolling-846f554989-8d65d(v2,ready=false) app-rolling-846f554989-95pg5(v2,ready=true) app-rolling-846f554989-pv4tn(v2,ready=true) app-rolling-c6b94689b-ffjmg(v1,ready=true) app-rolling-c6b94689b-tmplb(v1,ready=false)
08:46:10  app-rolling-846f554989-4f8lt(v2,ready=true) app-rolling-846f554989-8d65d(v2,ready=true) app-rolling-846f554989-95pg5(v2,ready=true) app-rolling-846f554989-pv4tn(v2,ready=true) app-rolling-c6b94689b-ffjmg(v1,ready=false)
08:46:11  app-rolling-846f554989-4f8lt(v2,ready=true) app-rolling-846f554989-8d65d(v2,ready=true) app-rolling-846f554989-95pg5(v2,ready=true) app-rolling-846f554989-pv4tn(v2,ready=true)
```

Count the `ready=true` entries on every line: **4, 4, 4, 4, 4, 4**. It never
drops below the desired count, and the pod total peaks at 5 — `maxSurge: 1` and
`maxUnavailable: 0` are doing exactly what they claim, observably.

Under load, the request timeline shows both versions serving simultaneously:

```
08:50:59.663  v1    (476 requests)
08:51:05.649  FAIL  (1 request)
08:51:05.662  v2    (1 request)
08:51:05.689  v1    (1 request)
...            v1 and v2 interleaving for ~11 seconds ...
08:51:16.837  v2    (73 requests)
```

**The service never stops answering.** Traffic lands on v1 and v2 alternately
for the ~11 seconds of the rollout, then settles on v2.

### The 5 failures are real, and worth understanding

They are not random: `rc=56` is *connection reset by peer* and `rc=28` is
*timeout*. They occur when a pod has begun shutting down but is still listed in
the Service endpoints — kube-proxy on every node needs a moment to be told the
pod is going away, and a request routed in that window hits a socket that is
already closing.

`maxUnavailable: 0` guarantees a **ready replica count**. It does not guarantee
**zero failed requests**, and those are genuinely different claims.

The standard mitigation is a `preStop` hook that makes the container sit still
while endpoint removal propagates:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 8"]
```

Measured with that hook: **4 failures in 517 requests**, versus 5 in 631 without
it. Honestly reported, that is **not a meaningful improvement** at this sample
size. The remaining errors on this cluster appear to come from kind's NodePort
path (host → node container → kube-proxy → conntrack) rather than from the
endpoint race the hook addresses. The hook is still correct practice on a real
cluster; this particular test bench just is not sensitive enough to demonstrate
its benefit, and claiming otherwise from this data would be overreading it.

### Strategy 2 — Recreate

```yaml
strategy:
  type: Recreate
```

This is the one strategy that is *supposed* to cause an outage: every old pod is
terminated before any new pod is created. The request log shows it exactly:

```
08:52:01.971  rc=0   v1
08:52:02.016  rc=0   v1
08:52:02.042  rc=0   v1
08:52:02.082  rc=0   v1        <-- last successful response
08:52:02.108  rc=56  FAIL
08:52:02.132  rc=56  FAIL
08:52:02.156  rc=56  FAIL
08:52:02.175  rc=56  FAIL
08:52:02.198  rc=56  FAIL
08:52:02.235  rc=56  FAIL
08:52:07.272  rc=28  FAIL      <-- a full 5s timeout; nothing answered at all
```

**Over five seconds with not one successful response.** v1 answered
continuously until `08:52:02.082`, then every subsequent request failed —
six immediate connection resets, then a request that hung for the full 5-second
timeout. This is a hard outage, qualitatively different from RollingUpdate's
isolated blips.

Use `Recreate` only when versions genuinely cannot coexist — an incompatible
database schema migration, or a `ReadWriteOnce` volume that only one pod can
mount.

### Strategy 3 — Blue-Green

Two complete Deployments run side by side, distinguished by a `track` label. One
Service selects one track; the "deployment" is a one-word edit to that selector.

```yaml
# app-live Service — the switch
selector:
  app: myapp
  track: blue      # change to green to cut over
```

```bash
$ kubectl get deploy -l app=myapp
NAME        READY   UP-TO-DATE   AVAILABLE   AGE
app-blue    3/3     3            3           3s
app-green   3/3     3            3           1s

$ kubectl get svc app-live -o jsonpath='{.spec.selector}'; echo
{"app":"myapp","track":"blue"}
```

Green is fully running and receiving no traffic at all — that is the window in
which you smoke-test a release against production infrastructure before any user
reaches it.

The cutover, and then a rollback, both performed under continuous load:

```bash
$ kubectl patch svc app-live -p '{"spec":{"selector":{"app":"myapp","track":"green"}}}'
service/app-live patched
```

```
total = 1019 requests, failed = 0

08:53:45.474  blue   (305 requests)
08:53:49.666  green  (441 requests)
08:53:55.773  blue   (273 requests)
```

**Zero failures, and zero interleaving.** Unlike RollingUpdate, there is no
period where both versions answer — request 305 got blue, request 306 got green.
The switch is atomic from the client's point of view, and the rollback at
`08:53:55` was equally instant, because blue never stopped running.

That is blue-green's real selling point: **rollback takes as long as an API
call**, not as long as a rollout. The cost is running double the pods.

### Strategy 4 — Canary

One Service deliberately selects a label that **both** deployments share,
ignoring `track` entirely:

```yaml
selector:
  app: myapp        # matches stable AND canary pods
```

Traffic share is then decided purely by the ratio of replica counts, because
kube-proxy load-balances evenly across all endpoints.

With **9 stable : 1 canary**:

```
endpoints backing the service: 10
total = 1026 requests, failed = 0

  blue     925 requests   90.2%
  green    101 requests    9.8%
```

Promoting the canary to **5 : 5**:

```
total = 916 requests, failed = 0

  blue     449 requests   49.0%
  green    467 requests   51.0%
```

90.2/9.8 and 49.0/51.0 against theoretical 90/10 and 50/50 — the replica ratio
*is* the traffic ratio, confirmed over ~2000 requests.

The limitation this exposes: **granularity is bounded by replica count.** A 1%
canary needs 99 stable pods. Getting finer control, or splitting on a header or
a cookie rather than at random, requires an ingress controller or a service
mesh — which is where [session 12](../12-ingress-configmaps-secrets/README.md)
picks up.

### Choosing between them

| | Downtime | Extra resources | Rollback speed | Both versions live? |
|---|---|---|---|---|
| **RollingUpdate** | Near-zero (5/631 here) | +`maxSurge` pods | A full rollout | Yes, briefly |
| **Recreate** | **Yes — 5s+ measured** | None | A full rollout | No |
| **Blue-Green** | **None — 0/1019** | **2× everything** | **Instant** | No (only one gets traffic) |
| **Canary** | **None — 0/1026** | +canary pods | Instant (scale to 0) | Yes, deliberately |

---

## Task 5 — DaemonSet: one pod per node

```bash
$ kubectl get ds node-logging-agent -o wide
NAME                 DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE   CONTAINERS   IMAGES         SELECTOR
node-logging-agent   2         2         2       2            2           <none>          2s    logger       busybox:1.36   app=node-logging-agent

$ kubectl get pods -l app=node-logging-agent -o custom-columns='POD:.metadata.name,NODE:.spec.nodeName,STATUS:.status.phase'
POD                        NODE                STATUS
node-logging-agent-bjb6z   devops-hw-worker    Running
node-logging-agent-flffr   devops-hw-worker2   Running
```

Note there is **no `replicas` field** in a DaemonSet — `DESIRED` is computed
from the number of eligible nodes. But the cluster has three nodes:

```bash
$ kubectl get nodes --no-headers | wc -l
       3
```

DESIRED is 2, not 3. The reason:

```bash
$ kubectl get node devops-hw-control-plane -o jsonpath='{.spec.taints}'; echo
[{"effect":"NoSchedule","key":"node-role.kubernetes.io/control-plane"}]
```

The control plane carries a `NoSchedule` taint and this DaemonSet has no
toleration for it. Compare with the DaemonSets Kubernetes ships itself:

```bash
$ kubectl get ds -n kube-system
NAME         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR            AGE
kindnet      3         3         3       3            3           kubernetes.io/os=linux   23m
kube-proxy   3         3         3       3            3           kubernetes.io/os=linux   23m
```

**3, not 2.** `kube-proxy` and `kindnet` tolerate the control-plane taint —
they have to, since the control-plane node needs networking and Service routing
just as much as any worker. This is the practical difference between "runs on
every node" and "runs on every node that will have it", and a real monitoring
agent would need those tolerations too or it would silently have no visibility
into the control plane.

Each pod learns its own node through the downward API:

```yaml
env:
  - name: NODE_NAME
    valueFrom:
      fieldRef:
        fieldPath: spec.nodeName
```

```bash
$ kubectl logs -l app=node-logging-agent --tail=2 --prefix
[pod/node-logging-agent-bjb6z/logger] [08:55:57] collecting metrics on node devops-hw-worker
[pod/node-logging-agent-flffr/logger] [08:55:57] collecting metrics on node devops-hw-worker2
```

---

## Task 6 — StatefulSet: stable identity

```bash
$ kubectl apply -f manifests/core-objects/statefulset.yaml
service/web-headless created
statefulset.apps/web-sts created
```

### Names are ordinal, and creation is ordered

```
08:56:09  web-sts-0(ContainerCreating)
08:56:10  web-sts-0(Running) web-sts-1(Running) web-sts-2(ContainerCreating)
08:56:11  web-sts-0(Running) web-sts-1(Running) web-sts-2(Running)
```

`web-sts-0` exists alone before `web-sts-1` is created. Names are
`<statefulset>-<ordinal>`, predictable in advance — unlike a Deployment's
`app-rolling-846f554989-pv4tn`, which you cannot know until it exists.

### Identity survives deletion — the IP does not

```bash
$ kubectl get pod web-sts-1 -o jsonpath='{.metadata.name} {.status.podIP}'; echo
web-sts-1 10.244.2.49

$ kubectl exec web-sts-1 -- cat /usr/share/nginx/html/index.html
served by web-sts-1

$ kubectl delete pod web-sts-1
pod "web-sts-1" deleted from default namespace

$ kubectl get pod web-sts-1 -o jsonpath='{.metadata.name} {.status.podIP}'; echo
web-sts-1 10.244.2.50

$ kubectl exec web-sts-1 -- cat /usr/share/nginx/html/index.html
served by web-sts-1
```

**Same name, different IP** (`.49` → `.50`). Compare with the Deployment in
session 09, where the replacement pod got a brand-new random name. The
StatefulSet's guarantee is the *name*, and that is precisely what a database
replica needs: `mysql-0` is always the primary, no matter how many times it is
rescheduled.

### Per-pod DNS through the headless Service

```bash
$ kubectl exec dnsutil -- nslookup web-headless.default.svc.cluster.local
Server:		10.96.0.10
Address:	10.96.0.10:53

Name:	web-headless.default.svc.cluster.local
Address: 10.244.1.64
Name:	web-headless.default.svc.cluster.local
Address: 10.244.1.63
Name:	web-headless.default.svc.cluster.local
Address: 10.244.2.50
```

A headless Service (`clusterIP: None`) returns **all three pod IPs**, not a
single virtual IP. And each pod is individually addressable:

```bash
$ kubectl exec dnsutil -- nslookup web-sts-0.web-headless.default.svc.cluster.local
Name:	web-sts-0.web-headless.default.svc.cluster.local
Address: 10.244.1.63

$ kubectl exec dnsutil -- nslookup web-sts-2.web-headless.default.svc.cluster.local
Name:	web-sts-2.web-headless.default.svc.cluster.local
Address: 10.244.1.64
```

`<pod>.<headless-svc>.<ns>.svc.cluster.local` resolves to exactly one pod. This
is how a replica finds *the primary specifically* rather than "some pod".

### Scale-down is reverse-ordered

```
08:56:44  web-sts-0(Running) web-sts-1(Running) web-sts-2(Terminating)
08:56:45  web-sts-0(Running) web-sts-1(Completed)
08:56:46  web-sts-0(Completed)
08:56:47
```

Highest ordinal first: 2, then 1, then 0. Scaling up goes 0→1→2 and scaling down
goes 2→1→0, so the lowest-numbered pod — conventionally the primary — is the
first created and the last destroyed.

---

## Task 7 — Two ways a selector can ruin your day

### Fail fast: selector does not match the pod template

```yaml
selector:
  matchLabels:
    app: frontend        # selector looks for app=frontend
template:
  metadata:
    labels:
      app: frontend-v2   # pods are labelled app=frontend-v2
```

```bash
$ kubectl apply -f manifests/troubleshooting/selector-mismatch.yaml
The Deployment "broken-selector" is invalid: spec.template.metadata.labels: Invalid value: {"app":"frontend-v2"}: `selector` does not match template `labels`
```

Rejected at admission time. Nothing was created. This is the *good* failure —
loud and immediate.

### Fail silent: a Service selector that matches nothing

Here the Deployment is correct and healthy; only the Service has a typo
(`app: api-service` instead of `app: api`):

```bash
$ kubectl get deploy api
NAME   READY   UP-TO-DATE   AVAILABLE   AGE
api    2/2     2            2           13s

$ kubectl get svc api-svc
NAME      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
api-svc   ClusterIP   10.96.115.247   <none>        80/TCP    13s
```

Both objects look perfectly healthy. `2/2` ready, Service has a ClusterIP. But:

```bash
$ kubectl get endpoints api-svc
NAME      ENDPOINTS   AGE
api-svc   <none>      13s
```

**`ENDPOINTS: <none>`.** Every request to this Service times out, while
`kubectl get all` shows nothing wrong. Kubernetes never validates that a Service
selector matches anything — an empty Service is a legitimate thing to create.

```bash
$ kubectl get pods -l app=api --show-labels
NAME                   READY   STATUS    RESTARTS   AGE   LABELS
api-787878dcdc-bggq5   1/1     Running   0          13s   app=api,pod-template-hash=787878dcdc
api-787878dcdc-jc55x   1/1     Running   0          13s   app=api,pod-template-hash=787878dcdc
```

The pods say `app=api`; the Service asked for `app=api-service`.

```bash
$ kubectl patch svc api-svc -p '{"spec":{"selector":{"app":"api"}}}'
service/api-svc patched

$ kubectl get endpoints api-svc
NAME      ENDPOINTS                       AGE
api-svc   10.244.1.66:80,10.244.2.51:80   16s
```

Fixed instantly, no restart. **`kubectl get endpoints` is the first command to
run whenever a Service does not respond** — it separates "my app is broken" from
"my selector is wrong" in one line.

---

## What I took away

- **Labels are the only wiring in Kubernetes.** A ReplicaSet deleted a pod it
  never created because a label matched; a Service silently served nothing
  because a label did not. There is no other coupling mechanism, which is both
  the elegance and the danger.
- **Measure downtime, do not assume it.** Establishing a 0/1596 baseline first
  is what made the rollout numbers meaningful. It also showed that
  `maxUnavailable: 0` guarantees *ready replicas*, not *zero failed requests* —
  and that my `preStop` hook did not measurably help on this particular cluster,
  which is worth stating rather than hiding.
- **`STATUS` is a summary, `status.phase` is the truth.** A CrashLoopBackOff pod
  is in phase `Running`; an ImagePullBackOff pod is in phase `Pending`. Alerting
  on the wrong one misses real outages.
- **Blue-green and canary are the same two Deployments** — the only difference is
  whether the Service selector includes the `track` label or not.
- **A Deployment rollback is an append, not a rewind**, and it leaves the
  `last-applied-configuration` annotation stale — a real trap in a GitOps flow.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Understand the Pod lifecycle | Done — all 5 phases deliberately provoked |
| 1 | Pending / CrashLoopBackOff / ImagePullBackOff | Done — incl. the live `Error` → `CrashLoopBackOff` flip |
| 1 | Init containers | Done — ordering and completion proven via shared volume |
| 1 | Multi-container pods | Done — sidecar updating a live volume, #26 → #27 |
| 1 | Every course lifecycle YAML (Running, readiness, liveness, startup, termination) | Done — 5 remaining files applied, status/details/output captured, explained |
| 2 | ReplicaSet | Done — incl. adoption experiment; controller deleted a foreign pod |
| 3 | Deployment | Done — Deployment → ReplicaSet → Pod chain shown |
| 3 | Rollout history and rollback | Done — incl. the stale-annotation warning and revision renumbering |
| 4 | Rolling update strategy | Done — measured, 5 failures / 631 requests, `maxUnavailable:0` verified per-second |
| 4 | Recreate strategy | Done — measured, **5+ second total outage** captured request-by-request |
| 4 | Blue-green deployment | Done — measured, **0 failures / 1019 requests**, instant cutover and rollback |
| 4 | Canary deployment | Done — measured, 9:1 → 90.2%/9.8%, 5:5 → 49.0%/51.0% |
| 5 | DaemonSet | Done — 2 of 3 nodes, taint explained, contrasted with `kube-proxy` |
| 6 | StatefulSet | Done — ordered creation, stable name with changed IP, per-pod DNS, reverse scale-down |
| 7 | Troubleshooting selectors | Done — fail-fast admission rejection vs silent empty-endpoints |

## Raw evidence

The [evidence directory](evidence/) preserves the original command transcripts,
including failed attempts and intermediate states. YAML listings are configuration,
and explanatory tables or shortened excerpts summarize those captures.
