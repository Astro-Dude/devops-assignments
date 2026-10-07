# Mini Project — Production-Ready Kubernetes Web App

Session 13, Task 3: *"Complete the mini project provided for Session 13."* The
course project (`devops-heros/session-13-storage-hpa-probes/mini-project/`)
combines a **PVC** for `/data`, an **HPA** (2–5 replicas at 50% CPU) and all
three **probes** on an nginx Deployment. The manifests here are the course
files, unchanged:

| File | What it creates |
|---|---|
| [`namespace.yaml`](namespace.yaml) | namespace `production-webapp` |
| [`pvc.yaml`](pvc.yaml) | `web-data`, 500Mi, RWO, default StorageClass |
| [`deployment.yaml`](deployment.yaml) | `web-app`: 2 × nginx 1.27, requests 100m/64Mi, limits 200m/128Mi, startup + readiness + liveness probes, PVC at `/data`, `strategy: Recreate` |
| [`service.yaml`](service.yaml) | `web-service`, ClusterIP :80 |
| [`hpa.yaml`](hpa.yaml) | `web-app-hpa`, min 2, max 5, 50% CPU |

The project was run on a single-node kind cluster (`hw-legacy`, with
metrics-server). The StorageClass is kind's `standard` (`rancher.io/local-path`)
instead of Minikube's `k8s.io/minikube-hostpath`, which the course diagram
assumes. Full real transcript:
[`../evidence/s13-mini-project.txt`](../evidence/s13-mini-project.txt).

---

## Step 5 — Deploy

```console
$ kubectl apply -f mini-project/namespace.yaml
namespace/production-webapp created

$ kubectl apply -f mini-project/pvc.yaml
persistentvolumeclaim/web-data created

$ kubectl -n production-webapp get pvc
NAME       STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
web-data   Pending                                      standard       <unset>                 0s

$ kubectl -n production-webapp describe pvc web-data | sed -n '/^Events:/,$p'
  Normal  WaitForFirstConsumer  0s    persistentvolume-controller  waiting for first consumer to be created before binding
```

The course's expected output shows `Bound` right away. Here it is `Pending`
until the Deployment exists, because kind's StorageClass uses
`WaitForFirstConsumer` (see [`../01-kubernetes-volumes`](../01-kubernetes-volumes/README.md#6-dynamic-provisioning)).
That is correct behaviour, not a fault (course troubleshooting Issue 1).

```console
$ kubectl apply -f mini-project/deployment.yaml -f mini-project/service.yaml
deployment.apps/web-app created
service/web-service created

$ kubectl -n production-webapp get pods -o wide
NAME                      READY   STATUS    RESTARTS   AGE   IP            NODE
web-app-d45775485-cbxq6   1/1     Running   0          13s   10.244.0.32   hw-legacy-control-plane
web-app-d45775485-hfdkx   1/1     Running   0          13s   10.244.0.33   hw-legacy-control-plane

$ kubectl -n production-webapp get pvc
NAME       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
web-data   Bound    pvc-80417924-edfd-4197-94de-c19ea7cfd7d7   500Mi      RWO            standard       13s

$ kubectl apply -f mini-project/hpa.yaml
horizontalpodautoscaler.autoscaling/web-app-hpa created

$ kubectl -n production-webapp get all
NAME                          READY   STATUS    RESTARTS   AGE
pod/web-app-d45775485-cbxq6   1/1     Running   0          53s
pod/web-app-d45775485-hfdkx   1/1     Running   0          53s

NAME                  TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
service/web-service   ClusterIP   10.96.77.99   <none>        80/TCP    53s

NAME                      READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-app   2/2     2            2           53s

NAME                                DESIRED   CURRENT   READY   AGE
replicaset.apps/web-app-d45775485   2         2         2       53s

NAME                                              REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/web-app-hpa   Deployment/web-app   cpu: 1%/50%   2         5         2          40s
```

The claim bound as soon as the first pod was scheduled. The HPA reads
`cpu: 1%/50%` (not `<unknown>`) because metrics-server is running and the pods
set `requests.cpu: 100m` (course troubleshooting Issue 2).

---

## Task 1 — Storage persistence

```console
$ kubectl -n production-webapp exec web-app-d45775485-cbxq6 -- sh -c 'echo "Student: Shaurya Verma (24BCS10151)" > /data/student.txt'

$ kubectl -n production-webapp exec web-app-d45775485-cbxq6 -- cat /data/student.txt
Student: Shaurya Verma (24BCS10151)

# the second replica mounts the same claim:
$ kubectl -n production-webapp exec web-app-d45775485-hfdkx -- cat /data/student.txt
Student: Shaurya Verma (24BCS10151)

$ kubectl -n production-webapp delete pod web-app-d45775485-cbxq6
pod "web-app-d45775485-cbxq6" deleted from production-webapp namespace

$ kubectl -n production-webapp get pods
NAME                      READY   STATUS    RESTARTS   AGE
web-app-d45775485-hfdkx   1/1     Running   0          62s
web-app-d45775485-rtgx6   1/1     Running   0          8s

$ kubectl -n production-webapp exec web-app-d45775485-rtgx6 -- cat /data/student.txt
Student: Shaurya Verma (24BCS10151)
```

The pod that wrote the file was deleted. Its replacement (`rtgx6`, 8 s old)
reads the same file, because the data lives on the PersistentVolume and not in
the pod. Both replicas can mount one **RWO** claim because RWO means one
*node*, and both pods are on the same node. On a multi-node cluster, a second
replica scheduled on a different node would get stuck in `ContainerCreating`
with an attach error. That is probably why the course Deployment uses
`strategy: Recreate`.

The same file was still there at the very end, after 3 HPA scale events and 4
rollouts: `kubectl exec deploy/web-app -- cat /data/student.txt` →
`Student: Shaurya Verma (24BCS10151)`.

---

## Task 2 — Service verification

The course uses `kubectl port-forward svc/web-service 8080:80`. On this
machine host port 8080 is already bound by the kind cluster's ingress mapping,
so the Service was tested from inside the cluster instead:

```console
$ kubectl -n production-webapp get endpointslices -l kubernetes.io/service-name=web-service
NAME                ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
web-service-64dn6   IPv4          80      10.244.0.33,10.244.0.46   62s

$ kubectl -n production-webapp run curl-test --rm -i --restart=Never --image=busybox:1.36 -- wget -q -O- http://web-service | head -4
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
```

The endpoint list is the two current pod IPs, and the `wget` above got the
nginx welcome page. (The transcript also shows a harmless warning that
`--rm -i` could not attach to the container because it had already exited, so
kubectl fell back to streaming its logs.)

---

## Task 3 — Trigger HPA elastic scaling

### One load generator: correctly **not** enough

The course's command:

```console
$ kubectl run load-generator -n production-webapp --image=busybox:1.36 --restart=Never -- /bin/sh -c 'while true; do wget -q -O- http://web-service; done'
pod/load-generator created

----- [19:04:56] t=150s -----
web-app-hpa   Deployment/web-app   cpu: 33%/50%   2     5     2     3m21s
web-app-d45775485-hfdkx   26m   12Mi
web-app-d45775485-rtgx6   29m   12Mi
----- [19:05:57] t=210s -----
web-app-hpa   Deployment/web-app   cpu: 38%/50%   2     5     2     4m22s
web-app-d45775485-hfdkx   38m   12Mi
web-app-d45775485-rtgx6   39m   12Mi
```

One busybox loop spread over two pods gave **33–38%** of the 100m request.
That is below the 50% target, so the HPA correctly kept 2 replicas for more
than 3 minutes. The course's expected output (110% within a minute) assumes
more load than one loop produces here.

### Three load generators: 2 → 4 → 5

```console
$ kubectl run load-generator-2 -n production-webapp --image=busybox:1.36 --restart=Never -- /bin/sh -c 'while true; do wget -q -O- http://web-service; done'
$ kubectl run load-generator-3 -n production-webapp --image=busybox:1.36 --restart=Never -- /bin/sh -c 'while true; do wget -q -O- http://web-service; done'

  time      TARGETS        REPLICAS   per-pod CPU (kubectl top pods)
  19:06:33  cpu: 40%/50%   2          39m 42m
  19:07:03  cpu: 87%/50%   2          79m 95m
  19:07:18  cpu: 37%/50%   4          21m 33m 11m 42m
  19:07:48  cpu: 55%/50%   4          53m 51m 59m 59m
  19:08:18  cpu: 60%/50%   4          63m 62m 63m 54m
  19:08:34  cpu: 63%/50%   5          63m 27m 63m 63m 63m
  19:09:04  cpu: 53%/50%   5          54m 54m 52m 53m 54m
```

(Condensed from the 15-second samples in the transcript. Each line is one real
`kubectl get hpa` + `kubectl top pods` sample.)

```console
$ kubectl -n production-webapp top pods
NAME                      CPU(cores)   MEMORY(bytes)
load-generator            780m         6Mi
load-generator-2          785m         5Mi
load-generator-3          781m         5Mi
web-app-d45775485-88rs8   54m          12Mi
web-app-d45775485-92p8d   52m          13Mi
web-app-d45775485-hfdkx   53m          12Mi
web-app-d45775485-qsn8z   54m          12Mi
web-app-d45775485-rtgx6   53m          12Mi

$ kubectl -n production-webapp describe hpa web-app-hpa
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  53% (53m) / 50%
Min replicas:                                          2
Max replicas:                                          5
Deployment pods:                                       5 current / 5 desired
Conditions:
  AbleToScale     True    ReadyForNewScale    recommended size matches current size
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange  the desired count is within the acceptable range
Events:
  Normal   SuccessfulRescale  2m59s  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale  104s   horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization (percentage of request) above target
```

At 87% on 2 pods the HPA computed `ceil(2 × 87/50) = 4`. On 4 pods at 63% it
computed `ceil(4 × 63/50) = 6`, capped at **maxReplicas 5**. With 5 pods the
average settled at 52–53%, within the HPA's default 10% tolerance of the 50%
target, so it stopped there.

### Stop the load and watch scale-down

```console
$ kubectl delete pod load-generator load-generator-2 load-generator-3 -n production-webapp

  19:10:36  cpu: 51%/50%  5
  19:10:51  cpu: 17%/50%  5
  19:11:06  cpu:  2%/50%  5
  ...       cpu:  1%/50%  5      (unchanged for ~5 minutes)
  19:15:39  cpu:  1%/50%  2

$ kubectl -n production-webapp describe hpa web-app-hpa | sed -n '/^Events:/,$p'
  Normal   SuccessfulRescale  10m    horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale  8m49s  horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale  93s    horizontal-pod-autoscaler  New size: 2; reason: All metrics below target
```

CPU dropped to 1% within 30 s, but the replicas stayed at 5 for about
**5 minutes**, and then dropped straight to the minimum of 2 in one step. That
is the default **300 s scale-down stabilisation window**: the HPA uses the
highest recommendation from the last 5 minutes, so a short dip in traffic does
not cause flapping.

---

## Bonus challenges

### Challenge 2 — readiness gating

```console
$ kubectl -n production-webapp patch deploy web-app --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/does-not-exist"}]'
deployment.apps/web-app patched

$ kubectl -n production-webapp get pods -l app=web-app
NAME                       READY   STATUS    RESTARTS   AGE
web-app-5945bfc776-k8m9b   0/1     Running   0          35s
web-app-5945bfc776-mmd6p   0/1     Running   0          35s

$ kubectl -n production-webapp get endpoints web-service
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME          ENDPOINTS   AGE
web-service               23m

$ kubectl -n production-webapp get endpointslices -l kubernetes.io/service-name=web-service -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}  ready={.conditions.ready}  serving={.conditions.serving}{"\n"}{end}'
10.244.0.101  ready=false  serving=false
10.244.0.102  ready=false  serving=false

$ kubectl -n production-webapp get events --field-selector reason=Unhealthy --sort-by=.lastTimestamp | tail -2
1s          Warning   Unhealthy   pod/web-app-5945bfc776-k8m9b   Readiness probe failed: HTTP probe failed with statuscode: 404
1s          Warning   Unhealthy   pod/web-app-5945bfc776-mmd6p   Readiness probe failed: HTTP probe failed with statuscode: 404

$ kubectl -n production-webapp logs curl-test2        # wget -T 3 http://web-service
wget: can't connect to remote host (10.96.77.99): Connection refused

$ kubectl -n production-webapp rollout undo deploy/web-app
$ kubectl -n production-webapp get endpoints web-service
NAME          ENDPOINTS                         AGE
web-service   10.244.0.104:80,10.244.0.105:80   23m
```

The pods are `Running` but `0/1`, the Service has no endpoints, and requests
to it are refused, exactly as the course predicts. Something I learned the
hard way: my first attempt checked `kubectl get endpointslices`, whose
`ENDPOINTS` column still listed both IPs. EndpointSlices keep **not-ready**
endpoints with `ready=false`, and only the conditions show they are excluded.
The deprecated `kubectl get endpoints` (or the jsonpath above) shows the real
routing state. Both attempts are in the transcript.

### Challenge 3 — liveness restart loop

```console
$ kubectl -n production-webapp patch deploy web-app --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/crash"}]'
deployment.apps/web-app patched

$ kubectl -n production-webapp get pods          (75 s later)
NAME                      READY   STATUS      RESTARTS      AGE
web-app-85d86b65d-nzzr7   1/1     Running     3 (13s ago)   74s
web-app-85d86b65d-wkjnf   1/1     Running     3 (13s ago)   74s

$ kubectl -n production-webapp get events --field-selector reason=Killing --sort-by=.lastTimestamp | tail -2
14s         Normal   Killing   pod/web-app-85d86b65d-wkjnf    Container nginx failed liveness probe, will be restarted
14s         Normal   Killing   pod/web-app-85d86b65d-nzzr7    Container nginx failed liveness probe, will be restarted
```

There were 3 restarts in 74 s, about one every 15 s. That is
`initialDelaySeconds 5` plus `periodSeconds 5 × failureThreshold 3`, as the
course says. Rolling back (`rollout undo`) restored 0-restart pods, and
`/data/student.txt` was still on the volume.

---

## What the mini project demonstrated

| Pillar | Evidence |
|---|---|
| State persistence | a file written by a deleted pod was read by its replacement, and was still there after 3 HPA scale events and 4 rollouts |
| Elastic scaling | 2 → 4 → 5 under load (capped at max), back to 2 after the 300 s stabilisation window |
| Health diagnostics | readiness failure removed pods from the Service without restarting them; liveness failure restarted them about every 15 s |
