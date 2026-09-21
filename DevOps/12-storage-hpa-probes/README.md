# Storage, Autoscaling & Probes — Homework

Session 13. Volumes and persistent storage, the Horizontal Pod Autoscaler under
a real load test, and the three probe types compared side by side on a single
timeline.

Command results are **real captured output** from the three-node kind cluster
built in [assignment 08](../08-kubernetes-fundamentals/README.md), with
`metrics-server` installed so the HPA has something to read.

---

## Task 1 — Ephemeral volumes

### emptyDir — shared between containers, dies with the pod

[`manifests/volumes/emptydir.yaml`](manifests/volumes/emptydir.yaml) runs two
containers sharing one `emptyDir`: a writer appending a line every 3 seconds, and
an idle reader.

```bash
$ kubectl exec emptydir-demo -c writer -- cat /shared/log.txt
line 1
line 2
line 3
line 4
line 5

$ kubectl exec emptydir-demo -c reader -- cat /shared/log.txt
line 1
line 2
line 3
line 4
line 5
```

Identical content from both containers — one volume, two mount points.

Now delete the pod and recreate it from the same manifest:

```bash
$ kubectl delete pod emptydir-demo
pod "emptydir-demo" deleted from default namespace

$ kubectl apply -f manifests/volumes/emptydir.yaml
pod/emptydir-demo created

$ kubectl exec emptydir-demo -c reader -- cat /shared/log.txt
line 1
line 2
```

**The counter restarted from 1.** The previous five lines are gone permanently.
An `emptyDir` is created when the pod is assigned to a node and deleted when the
pod leaves it — it survives a *container* crash, never a *pod* deletion.

Good for: scratch space, caches, and handing files between containers in one pod
(the sidecar pattern in [assignment 09](../09-k8s-core-objects/README.md)).

### hostPath — a real directory on the node

```yaml
volumes:
  - name: host-data
    hostPath:
      path: /tmp/k8s-hostpath-demo
      type: DirectoryOrCreate
```

```bash
$ kubectl exec hostpath-demo -- sh -c 'echo "written from inside the pod" > /host-data/from-pod.txt'
$ kubectl exec hostpath-demo -- cat /host-data/from-pod.txt
written from inside the pod
```

The proof that this is genuinely the node's filesystem — reading it from
**outside Kubernetes entirely**, straight from the node container:

```bash
$ docker exec devops-hw-worker cat /tmp/k8s-hostpath-demo/from-pod.txt
written from inside the pod
```

And the reverse direction:

```bash
$ docker exec devops-hw-worker sh -c 'echo "written from the node" > /tmp/k8s-hostpath-demo/from-node.txt'

$ kubectl exec hostpath-demo -- ls -l /host-data
total 8
-rw-r--r--    1 root     root            22 Sep 21 09:24 from-node.txt
-rw-r--r--    1 root     root            28 Sep 21 09:24 from-pod.txt

$ kubectl exec hostpath-demo -- cat /host-data/from-node.txt
written from the node
```

Fully bidirectional. That is exactly why `hostPath` is dangerous: a pod that can
mount `/` or `/var/run/docker.sock` effectively owns the node. It is also why
this pod had to be pinned with `nodeName: devops-hw-worker` — the data lives on
one specific machine, so the moment the pod is rescheduled elsewhere it silently
sees an empty directory.

Legitimate uses are node-level agents: log collectors reading `/var/log`,
monitoring agents reading `/proc`. For application data, use a PersistentVolume.

---

## Task 2 — Persistent storage, provisioned by hand

### The three objects and how they relate

```
   ADMIN                          DEVELOPER                    POD
     │                                │                         │
  PersistentVolume              PersistentVolumeClaim      volumes:
  "here is 1Gi of               "I need 500Mi of            persistentVolumeClaim:
   storage that exists"          RWO storage"                 claimName: ...
     │                                │                         │
     └────────────► BOUND ◄───────────┘                         │
                      │                                         │
                      └─────────────────────────────────────────┘
```

A PVC is a **request**; a PV is **supply**. The control plane matches them.

```bash
$ kubectl apply -f manifests/persistent/01-static-pv.yaml
persistentvolume/manual-pv created

$ kubectl get pv manual-pv
NAME        CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
manual-pv   1Gi        RWO            Retain           Available           manual         <unset>                          0s
```

`STATUS: Available` — supply exists, nothing has claimed it.

```bash
$ kubectl apply -f manifests/persistent/02-static-pvc.yaml
persistentvolumeclaim/manual-pvc created

$ kubectl get pv,pvc
NAME                         CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
persistentvolume/manual-pv   1Gi        RWO            Retain           Bound    default/manual-pvc   manual         <unset>                          6s

NAME                               STATUS   VOLUME      CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/manual-pvc   Bound    manual-pv   1Gi        RWO            manual         <unset>                 6s
```

Both flipped to `Bound`, pointing at each other.

### Binding is not exact matching

```bash
$ kubectl get pvc manual-pvc -o jsonpath='requested={.spec.resources.requests.storage} bound={.status.capacity.storage} volume={.spec.volumeName}'; echo
requested=500Mi bound=1Gi volume=manual-pv
```

**The claim asked for 500Mi and got 1Gi.** A PVC binds to any PV that is *at
least* as large with compatible access modes — and the extra 512Mi is simply
wasted, since no second claim can use the same PV. This is the main argument
against static provisioning at any scale.

### The data actually persists

```bash
$ kubectl exec static-storage-pod -- sh -c 'echo "persistent data written at $(date -u +%H:%M:%S)" > /data/important.txt'
$ kubectl exec static-storage-pod -- cat /data/important.txt
persistent data written at 09:24:58

$ kubectl delete pod static-storage-pod
pod "static-storage-pod" deleted from default namespace

$ kubectl apply -f manifests/persistent/03-static-pod.yaml
pod/static-storage-pod created

$ kubectl exec static-storage-pod -- cat /data/important.txt
persistent data written at 09:24:58
```

**The identical timestamp, `09:24:58`, after the pod was destroyed and
recreated.** Compare directly with the emptyDir test in Task 1, where the same
experiment lost everything. The PVC outlived the pod; that is the entire point.

---

## Task 3 — Dynamic provisioning with a StorageClass

```bash
$ kubectl get storageclass
NAME                 PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
standard (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  53m
```

Three fields in that one line determine everything that follows:

- **`PROVISIONER: rancher.io/local-path`** — the component that creates volumes
  on demand. On a cloud this would be `ebs.csi.aws.com` or `pd.csi.storage.gke.io`.
- **`RECLAIMPOLICY: Delete`** — when the PVC is deleted, the PV **and the data**
  are destroyed. Note the hand-made PV above used `Retain` instead.
- **`VOLUMEBINDINGMODE: WaitForFirstConsumer`** — do not create the volume until a
  pod actually needs it.

### WaitForFirstConsumer, observed

```bash
$ kubectl apply -f manifests/persistent/04-dynamic-pvc.yaml
persistentvolumeclaim/dynamic-pvc created

$ kubectl get pvc dynamic-pvc
NAME          STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
dynamic-pvc   Pending                                      standard       <unset>                 6s
```

**Pending, and that is correct** — not a fault:

```bash
$ kubectl describe pvc dynamic-pvc | sed -n '/^Events:/,$p'
Events:
  Type    Reason                Age              From                         Message
  ----    ------                ----             ----                         -------
  Normal  WaitForFirstConsumer  0s (x2 over 6s)  persistentvolume-controller  waiting for first consumer to be created before binding
```

The reason this mode exists: a volume is created in one availability zone (or on
one node). If it were created before the pod was scheduled, the scheduler might
later place the pod somewhere it cannot reach the volume. Waiting lets the
scheduler choose the node first, and the volume is then created in the right
place.

### Creating a consumer

```bash
$ kubectl apply -f manifests/persistent/05-dynamic-deploy.yaml
deployment.apps/dynamic-storage created

$ kubectl get pvc dynamic-pvc
NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
dynamic-pvc   Bound    pvc-aa7f8795-8a90-4708-9d4b-d3988f54aa8c   1Gi        RWO            standard       <unset>                 11s
```

```bash
$ kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                 STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
manual-pv                                  1Gi        RWO            Retain           Bound    default/manual-pvc    manual         <unset>                          64s
pvc-aa7f8795-8a90-4708-9d4b-d3988f54aa8c   1Gi        RWO            Delete           Bound    default/dynamic-pvc   standard       <unset>                          2s
```

**Nobody wrote YAML for that second PV.** It was created automatically, named
after the claim's UID, and — importantly — it inherited `RECLAIM POLICY: Delete`
from the StorageClass, whereas the hand-made one kept `Retain`. Delete a
`dynamic-pvc` and the data is gone; delete `manual-pvc` and the data survives for
manual recovery.

The whole provisioning chain is in the events:

```bash
$ kubectl describe pvc dynamic-pvc | sed -n '/^Events:/,$p'
Events:
  Type    Reason                 Age               From                                      Message
  ----    ------                 ----              ----                                      -------
  Normal  WaitForFirstConsumer   5s (x2 over 11s)  persistentvolume-controller               waiting for first consumer to be created before binding
  Normal  ExternalProvisioning   5s                persistentvolume-controller               Waiting for a volume to be created either by the external provisioner 'rancher.io/local-path' or manually by the system administrator. If volume creation is delayed, please verify that the provisioner is running and correctly registered.
  Normal  Provisioning           5s                rancher.io/local-path_local-path-provisioner-75f7fc7dc5-pl9n4_...  External provisioner is provisioning volume for claim "default/dynamic-pvc"
  Normal  ProvisioningSucceeded  2s                rancher.io/local-path_local-path-provisioner-75f7fc7dc5-pl9n4_...  Successfully provisioned volume pvc-aa7f8795-8a90-4708-9d4b-d3988f54aa8c
```

Four steps, three seconds, no administrator involved. That is why nobody does
static provisioning in production.

| | Static | Dynamic |
|---|---|---|
| Who creates the PV | a human, in advance | the provisioner, on demand |
| Capacity waste | yes — 500Mi claim took a 1Gi PV | none — exactly what was asked |
| Reclaim policy here | `Retain` (data survives) | `Delete` (data destroyed with the PVC) |
| Scales to hundreds of apps | no | yes |

---

## Task 4 — The three probes, on one timeline

Four pods were applied simultaneously and sampled every 5 seconds. All four
manifests are in [`manifests/probes/`](manifests/probes/).

| Pod | What it does | Probe |
|---|---|---|
| `readiness-demo` | `/ready` appears after 20s | readiness only |
| `liveness-demo` | `/healthz` **disappears** after 30s | liveness only |
| `startup-demo` | takes 40s to boot | startup **+** liveness |
| `no-startup-demo` | takes 40s to boot — identical | liveness **only** |

The last two are the controlled experiment: the same slow container, differing
only in whether a startup probe protects it.

```
 sec  readiness-demo        liveness-demo         startup-demo          no-startup-demo       endpoints
  10s  0/1 Running   r=0  |  1/1 Running   r=0  |  0/1 Running   r=0  |  1/1 Running   r=0  |  (none)
  20s  0/1 Running   r=0  |  1/1 Running   r=0  |  0/1 Running   r=0  |  1/1 Running   r=0  |  (none)
  25s  0/1 Running   r=0  |  1/1 Running   r=0  |  0/1 Running   r=0  |  1/1 Running   r=0  |  (none)
  30s  1/1 Running   r=0  |  1/1 Running   r=0  |  0/1 Running   r=0  |  1/1 Running   r=0  |  10.244.2.63
  45s  1/1 Running   r=0  |  1/1 Running   r=1  |  0/1 Running   r=0  |  1/1 Running   r=1  |  10.244.2.63
  50s  1/1 Running   r=0  |  1/1 Running   r=1  |  1/1 Running   r=0  |  1/1 Running   r=1  |  10.244.2.63
  85s  1/1 Running   r=0  |  1/1 Running   r=2  |  1/1 Running   r=0  |  1/1 Running   r=2  |  10.244.2.63
 125s  1/1 Running   r=0  |  1/1 Running   r=3  |  1/1 Running   r=0  |  1/1 Running   r=3  |  10.244.2.63
 150s  1/1 Running   r=0  |  1/1 Running   r=3  |  1/1 Running   r=0  |  1/1 Running   r=3  |  10.244.2.63
```

(`r=` is the restart count; `endpoints` is the Service backing `readiness-demo`.)

### Readiness — controls traffic, never restarts

For the first 25 seconds `readiness-demo` is `0/1` and the Service has **no
endpoints at all**. At 30s it becomes `1/1` and `10.244.2.63` appears.

```bash
$ kubectl get pod readiness-demo -o jsonpath='restartCount={.status.containerStatuses[0].restartCount} ready={.status.containerStatuses[0].ready}'; echo
restartCount=0 ready=true

$ kubectl describe pod readiness-demo | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                    From               Message
  ----     ------     ----                   ----               -------
  Normal   Scheduled  2m50s                  default-scheduler  Successfully assigned default/readiness-demo to devops-hw-worker2
  Normal   Started    2m50s                  kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  2m31s (x6 over 2m46s)  kubelet            spec.containers{web}: Readiness probe failed: HTTP probe failed with statuscode: 404
```

The probe failed **six times** and the restart count is **0**. There is no
`Killing` event. Readiness failure removes the pod from Service endpoints and
does nothing else — which is exactly what makes zero-downtime rolling updates
possible.

### Liveness — restarts the container

```bash
$ kubectl describe pod liveness-demo | sed -n '/^Events:/,$p'
Events:
  Type     Reason     Age                 From               Message
  ----     ------     ----                ----               -------
  Normal   Scheduled  2m49s               default-scheduler  Successfully assigned default/liveness-demo to devops-hw-worker
  Normal   Created    9s (x5 over 2m49s)  kubelet            spec.containers{web}: Container created
  Normal   Started    9s (x5 over 2m49s)  kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  9s (x8 over 2m14s)  kubelet            spec.containers{web}: Liveness probe failed: HTTP probe failed with statuscode: 404
  Normal   Killing    9s (x4 over 2m9s)   kubelet            spec.containers{web}: Container web failed liveness probe, will be restarted
```

**`Killing … will be restarted`** — the event readiness never produces. The
container is recreated roughly every 40 seconds, forever: it boots, serves
`/healthz` for 30s, deletes it, gets killed, and repeats.

The health endpoint returning 404 is what "deadlocked but still listening"
looks like: the process is alive, the port is open, and the application is
useless. An HTTP liveness probe can catch that — a plain
"is the process running" check would see nothing wrong.

### Startup — the controlled experiment

Both slow pods take exactly 40 seconds to boot. `startup-demo` has a startup
probe; `no-startup-demo` does not.

```bash
$ kubectl get pods readiness-demo liveness-demo startup-demo no-startup-demo
NAME              READY   STATUS    RESTARTS     AGE
readiness-demo    1/1     Running   0            2m50s
liveness-demo     1/1     Running   4 (9s ago)   2m50s
startup-demo      1/1     Running   0            2m50s
no-startup-demo   1/1     Running   4 (9s ago)   2m50s
```

**`startup-demo`: 0 restarts. `no-startup-demo`: 4 restarts.** Same image, same
boot time, same liveness probe.

```bash
$ kubectl describe pod no-startup-demo | sed -n '/^Events:/,$p'
Events:
  Normal   Killing    39s (x4 over 2m39s)  kubelet  spec.containers{web}: Container web failed liveness probe, will be restarted
  Warning  Unhealthy  4s (x9 over 2m44s)   kubelet  spec.containers{web}: Liveness probe failed: Get "http://10.244.1.79:80/healthz": dial tcp 10.244.1.79:80: connect: connection refused
```

The liveness probe (`initialDelaySeconds: 5`, `periodSeconds: 5`,
`failureThreshold: 2`) gives up after ~15 seconds. The app needs 40. It is killed
before it can ever finish starting — **a permanent crash loop caused entirely by
a misconfigured probe, not by a broken application.**

```bash
$ kubectl describe pod startup-demo | sed -n '/^Events:/,$p'
Events:
  Normal   Scheduled  2m49s                 default-scheduler  Successfully assigned default/startup-demo to devops-hw-worker2
  Normal   Started    2m49s                 kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  2m9s (x8 over 2m44s)  kubelet            spec.containers{web}: Startup probe failed: Get "http://10.244.2.64:80/healthz": dial tcp 10.244.2.64:80: connect: connection refused

$ kubectl get pod startup-demo -o jsonpath='restartCount={.status.containerStatuses[0].restartCount}'; echo
restartCount=0
```

The startup probe **also failed eight times** — but there is **no `Killing`
event**, because `failureThreshold: 20 × periodSeconds: 5` allows 100 seconds.
And crucially, **while a startup probe is running, the liveness probe is
disabled entirely.** Once the startup probe finally succeeds, liveness takes over
with its normal, aggressive settings.

| | Readiness | Liveness | Startup |
|---|---|---|---|
| On failure | removed from endpoints | **container restarted** | container restarted |
| Restart count here | **0** (6 failures) | 4 | **0** (8 failures) |
| Runs | continuously | continuously | **only until it first succeeds** |
| Fixes | "not ready for traffic yet" | deadlocks, hangs | **slow startup** |

The rule of thumb this proves: **if an app is slow to start, add a startup probe
— do not just widen the liveness probe**, because widening liveness also makes it
slower to detect a genuine deadlock for the rest of the pod's life.

---

## Task 5 — Horizontal Pod Autoscaler, under real load

### Why the resource request is mandatory

```yaml
resources:
  requests:
    cpu: 200m      # <-- the HPA's denominator
  limits:
    cpu: 500m
```

The HPA target is `averageUtilization: 50`, which means **50% of the request**,
not 50% of a core. With a 200m request, the target is 100m per pod. Without a
`requests.cpu` there is no denominator and the HPA cannot compute anything at
all — the single most common reason an HPA sits at `<unknown>/50%`.

```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0
  scaleDown:
    stabilizationWindowSeconds: 60    # default is 300s; shortened for this demo
```

```bash
$ kubectl get hpa php-apache
NAME         REFERENCE               TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
php-apache   Deployment/php-apache   cpu: 0%/50%   1         10        1          46s
```

### Applying load

Three pods hammering the Service in a tight loop:

```bash
$ kubectl run load-gen-1 --image=busybox:1.36 --restart=Never -- \
    /bin/sh -c "while true; do wget -q -O- http://php-apache; done"
```

Sampling every 15 seconds:

```
  15s  pods=1   cpu=[1m]
  30s  pods=1   cpu=[284m]
  45s  pods=3   cpu=[494m]
  60s  pods=5   cpu=[364m 422m]
  75s  pods=8   cpu=[192m 261m 247m 334m 229m]
  90s  pods=8   cpu=[134m 261m 171m 247m 227m 251m 145m 179m]
 105s  pods=10  cpu=[215m 240m 136m 160m 207m 166m 198m 156m]
 120s  pods=10  cpu=[136m 146m 279m 164m 160m 131m 135m 128m 124m 228m]
 135s  pods=10  cpu=[137m 138m 176m 180m 158m 161m 192m 174m 150m 144m]
```

Watch the per-pod CPU fall as replicas rise: a single pod at **494m** (247% of
its 200m request), then eight pods averaging ~230m, then ten averaging ~160m.
The HPA is doing arithmetic, not guessing.

### The controller's own decision log

```bash
$ kubectl describe hpa php-apache | sed -n '/^Events:/,$p'
Events:
  Type     Reason                        Age                   From                       Message
  ----     ------                        ----                  ----                       -------
  Warning  FailedGetResourceMetric       6m2s (x2 over 6m18s)  horizontal-pod-autoscaler  failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
  Warning  FailedComputeMetricsReplicas  6m2s (x2 over 6m18s)  horizontal-pod-autoscaler  invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
  Warning  FailedGetResourceMetric       5m47s                 horizontal-pod-autoscaler  failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready)
  Normal   SuccessfulRescale             5m2s                  horizontal-pod-autoscaler  New size: 3; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             4m47s                 horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             4m32s                 horizontal-pod-autoscaler  New size: 8; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             4m2s                  horizontal-pod-autoscaler  New size: 10; reason: cpu resource utilization (percentage of request) above target
```

**1 → 3 → 5 → 8 → 10.** Those first `FailedGetResourceMetric` warnings are worth
noting rather than hiding: for the first ~30 seconds metrics-server had not yet
scraped the new pods, so the HPA genuinely could not compute a target. They are
normal at startup and resolve on their own — but an HPA that shows them
*permanently* means metrics-server is missing or broken.

### Hitting the ceiling

```bash
$ kubectl get hpa php-apache
NAME         REFERENCE               TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
php-apache   Deployment/php-apache   cpu: 71%/50%   1         10        10         6m17s
```

```bash
$ kubectl describe hpa php-apache | sed -n '/^Metrics:/,/^Events:/p'
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  71% (142m) / 50%
Min replicas:                                          1
Max replicas:                                          10
Behavior:
  Scale Up:
    Stabilization Window: 0 seconds
    Select Policy: Max
    Policies:
      - Type: Pods     Value: 4    Period: 15 seconds
      - Type: Percent  Value: 100  Period: 15 seconds
  Scale Down:
    Stabilization Window: 60 seconds
    Select Policy: Max
    Policies:
      - Type: Percent  Value: 100  Period: 15 seconds
Deployment pods:       10 current / 10 desired
Conditions:
  Type            Status  Reason            Message
  ----            ------  ------            -------
  AbleToScale     True    ReadyForNewScale  recommended size matches current size
  ScalingActive   True    ValidMetricFound  the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  True    TooManyReplicas   the desired replica count is more than the maximum replica count
```

**`ScalingLimited: True — TooManyReplicas`.** CPU is stuck at 71%, above the 50%
target, and the HPA *wants* more pods but `maxReplicas: 10` forbids it. That
condition is the thing to alert on: it means the autoscaler has given up and the
service is now running hot.

Note also the default scale-up policies that were never written in the manifest:
**+4 pods or +100% every 15 seconds, whichever is larger**. These policies cap the rate of growth; the measured utilization and ready-pod
metrics determine the actual 1 → 3 → 5 → 8 → 10 recommendations.

### Scale down

```bash
$ kubectl delete pod load-gen-1 load-gen-2 load-gen-3
```

```
  15s  targets=55%/50%  replicas=10  actual_pods=10
  30s  targets=74%/50%  replicas=10  actual_pods=10
  45s  targets=16%/50%  replicas=10  actual_pods=10
  60s  targets=0%/50%   replicas=10  actual_pods=10
  75s  targets=1%/50%   replicas=10  actual_pods=10
  90s  targets=2%/50%   replicas=4   actual_pods=4
 105s  targets=1%/50%   replicas=1   actual_pods=1
```

```bash
  Normal   SuccessfulRescale   27s   horizontal-pod-autoscaler  New size: 4; reason: All metrics below target
  Normal   SuccessfulRescale   12s   horizontal-pod-autoscaler  New size: 1; reason: All metrics below target
```

CPU hit 0% at 60 seconds, but **nothing happened for another 30 seconds.** That
is the `stabilizationWindowSeconds: 60` doing its job: the HPA looks at the
highest recommendation over the whole window before shrinking, so a momentary
dip in traffic cannot cause it to drop pods that are about to be needed again.

**Scale-up is deliberately fast and scale-down deliberately slow** — the cost of
being slightly over-provisioned is much lower than the cost of dropping requests.
The real default is **300 seconds**; 60 was used here only so the demo finished.

---

## What I took away

- **emptyDir vs PVC is a one-experiment difference.** Same delete-and-recreate
  test: the emptyDir counter restarted at 1, the PVC still held `09:24:58`.
- **`hostPath` is genuinely the node's disk** — written from the pod, read with
  `docker exec`, and back again. That is its use case and its danger in one.
- **`WaitForFirstConsumer` means a Pending PVC is often correct**, not broken.
- **The reclaim policy decides whether your data survives**, and static vs
  dynamic provisioning defaulted to opposite answers (`Retain` vs `Delete`).
- **Readiness does not restart containers; repeated liveness failures do.** Six readiness
  failures → 0 restarts; eight liveness failures → 4 restarts.
- **A startup probe is not optional for a slow app.** Two identical containers,
  40-second boot: 0 restarts with one, a permanent crash loop without it.
- **An HPA with no `resources.requests` cannot work** — utilisation is a
  percentage of the request, so there is otherwise no denominator.
- **`ScalingLimited: TooManyReplicas` is the condition worth alerting on**: the
  autoscaler wanted more capacity and was not allowed to have it.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | emptyDir volume | Done — shared across 2 containers; data loss on pod delete proven |
| 1 | hostPath volume | Done — bidirectional read/write verified via `docker exec` on the node |
| 2 | PersistentVolume (static) | Done — `manual-pv`, Available → Bound |
| 2 | PersistentVolumeClaim | Done — 500Mi request bound a 1Gi PV; waste explained |
| 2 | Prove data persists | Done — same timestamp survived pod deletion and recreation |
| 3 | StorageClass / dynamic provisioning | Done — PV auto-created, full 4-event provisioning chain captured |
| 3 | Understand `WaitForFirstConsumer` | Done — Pending until a consumer existed, with the reason |
| 3 | Reclaim policies | Done — `Retain` vs `Delete` contrasted on live objects |
| 4 | Readiness probe | Done — endpoint appeared only at 30s; **0 restarts after 6 failures** |
| 4 | Liveness probe | Done — `Killing … will be restarted`, 4 restarts |
| 4 | Startup probe | Done — **controlled experiment: 0 restarts vs 4 on identical containers** |
| 5 | Create an HPA | Done — `autoscaling/v2`, 50% CPU target, min 1 max 10 |
| 5 | Generate load and observe scale-up | Done — **1 → 3 → 5 → 8 → 10** with per-pod CPU measured throughout |
| 5 | Observe scale-down | Done — 10 → 4 → 1, with the 60s stabilisation window visible |
| 5 | Understand HPA limits | Done — `ScalingLimited: TooManyReplicas` at 71%/50% |

## Raw evidence

The [evidence directory](evidence/) preserves the original command transcripts,
including failed attempts and intermediate states. YAML listings are configuration,
and explanatory tables or shortened excerpts summarize those captures.
