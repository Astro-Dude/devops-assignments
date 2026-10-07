# Kubernetes Object Comparison

Session 11, Task 2. Three comparisons the spec asks for:

1. Deployment vs ReplicaSet
2. Deployment vs DaemonSet vs StatefulSet
3. ReplicaSet vs Service

Each comparison has a table and a short live demo. Command results are **real
captured output** from a single-node kind cluster (`hw-legacy`, Kubernetes
v1.37), namespace `s11-compare`. Manifests are in [`manifests/`](manifests/).
The full transcript is
[`../evidence/s11-object-comparison.txt`](../evidence/s11-object-comparison.txt).

---

## 1. Deployment vs ReplicaSet

| | ReplicaSet | Deployment |
|---|---|---|
| **Purpose** | Keep exactly N copies of one Pod template running | Manage releases of an app: versions, rollout, rollback |
| **Pod management** | Creates and deletes Pods directly, matched by label selector | Never touches Pods; it creates and scales **ReplicaSets**, and they manage the Pods |
| **Scaling** | `spec.replicas` | `spec.replicas`, passed down to the current ReplicaSet |
| **Rolling updates** | None. Changing the template does not touch existing Pods | Built in: a new ReplicaSet for the new template, scaled up while the old one is scaled down (`maxSurge` / `maxUnavailable`) |
| **Rollback** | None | `kubectl rollout undo`. Old ReplicaSets are kept at 0 replicas (`revisionHistoryLimit`, default 10) |
| **Use it directly?** | Almost never | Yes, for every stateless app |

**Relationship:** Deployment → owns → ReplicaSet(s) → own → Pods. One
ReplicaSet per Pod-template revision. The `pod-template-hash` label keeps the
ReplicaSets apart.

### Demo: the ownership chain

```console
$ kubectl apply -f manifests/01-deployment.yaml
deployment.apps/web created

$ kubectl get rs -l app=web -o jsonpath='{range .items[*]}ReplicaSet {.metadata.name} is owned by {.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}{end}'
ReplicaSet web-68ccc9d8fd is owned by Deployment/web

$ kubectl get pods -l app=web -o jsonpath='{range .items[*]}Pod {.metadata.name} is owned by {.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}{end}'
Pod web-68ccc9d8fd-g27rp is owned by ReplicaSet/web-68ccc9d8fd
Pod web-68ccc9d8fd-tmwpr is owned by ReplicaSet/web-68ccc9d8fd
```

The Pods belong to the ReplicaSet, **not** to the Deployment. `ownerReferences`
shows the chain directly.

### Demo: who is in charge of scaling

```console
$ kubectl scale deploy/web --replicas=3
deployment.apps/web scaled

$ kubectl get rs -l app=web
NAME             DESIRED   CURRENT   READY   AGE
web-68ccc9d8fd   3         3         3       2s

$ kubectl scale rs -l app=web --replicas=1      # go around the Deployment
replicaset.apps/web-68ccc9d8fd scaled

$ kubectl get rs -l app=web                     # 3 seconds later
NAME             DESIRED   CURRENT   READY   AGE
web-68ccc9d8fd   3         3         3       5s
```

Scaling the ReplicaSet by hand was **reverted within 3 seconds**. The
Deployment controller saw its ReplicaSet at 1 when the Deployment says 3, and
set it back. When a ReplicaSet belongs to a Deployment, you always change the
Deployment.

### Demo: a rolling update creates a second ReplicaSet

```console
$ kubectl set image deploy/web nginx=nginx:1.27
deployment.apps/web image updated

$ kubectl rollout status deploy/web
Waiting for deployment "web" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "web" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "web" rollout to finish: 1 old replicas are pending termination...
deployment "web" successfully rolled out

$ kubectl get rs -l app=web -o wide
NAME             DESIRED   CURRENT   READY   AGE   CONTAINERS   IMAGES              SELECTOR
web-6759f89cbb   3         3         3       1s    nginx        nginx:1.27          app=web,pod-template-hash=6759f89cbb
web-68ccc9d8fd   0         0         0       6s    nginx        nginx:1.27-alpine   app=web,pod-template-hash=68ccc9d8fd

$ kubectl rollout history deploy/web
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
```

There are now two ReplicaSets, one per template. The old one is kept at
`DESIRED 0`, so it still records the previous template. `rollout undo` scales
it back up. A bare ReplicaSet cannot do any of this, which is why you use a
Deployment.

---

## 2. Deployment vs DaemonSet vs StatefulSet

| | Deployment | DaemonSet | StatefulSet |
|---|---|---|---|
| **Use cases** | Stateless apps: web, APIs, workers | One agent per node: log shippers, node exporters, CNI, kube-proxy | Stateful apps that need identity: databases, Kafka, ZooKeeper, Elasticsearch |
| **Pod creation** | N interchangeable Pods with random names (`web-6759f89cbb-xxxxx`), created in parallel | One Pod per matching node, created automatically when a node joins | Ordered, one at a time: `db-0`, then `db-1`; each waits for the previous to be Ready |
| **Pod names** | Random, change on replacement | Random | **Stable ordinals**, kept when the Pod is replaced |
| **Scaling** | `kubectl scale` / HPA | No `replicas`: the number of Pods follows the number of nodes (use nodeSelector/affinity/taints to limit) | `kubectl scale`. Scale-down removes the highest ordinal first |
| **Networking** | Pods behind a normal ClusterIP Service; individual Pods not addressable by name | Often `hostNetwork`/`hostPort`, reached per node | **Headless Service** gives each Pod a DNS name: `db-0.db.<ns>.svc.cluster.local` |
| **Storage** | Shared PVC or none; every replica identical | Usually `hostPath` (it is node-level software) | `volumeClaimTemplates`: **one PVC per Pod** (`data-db-0`, `data-db-1`), re-attached to the same ordinal, **kept after scale-down** |
| **Update strategy** | RollingUpdate / Recreate | RollingUpdate / OnDelete, node by node | RollingUpdate in reverse ordinal order (supports `partition`) / OnDelete |
| **Examples** | nginx front end, REST API | fluent-bit, node-exporter, kube-proxy, kindnet | PostgreSQL primary/replicas, Kafka brokers, Redis cluster |

### Demo: DaemonSet, one Pod per node, no `scale`

```console
$ kubectl get nodes
NAME                      STATUS   ROLES           AGE   VERSION
hw-legacy-control-plane   Ready    control-plane   23m   v1.37.0

$ kubectl get ds node-agent
NAME         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
node-agent   1         1         1       1            1           <none>          1s

$ kubectl logs -l app=node-agent
agent on hw-legacy-control-plane

$ kubectl scale ds/node-agent --replicas=3
Error from server (NotFound): the server could not find the requested resource
```

`DESIRED 1` because the cluster has one node. Nobody set that number. `kubectl
scale` fails because a DaemonSet has no `scale` subresource; the only way to
get more Pods is to add nodes. (In session 10 a DaemonSet on the 3-node cluster got 2
Pods, because the control-plane taint kept it off one node.)

### Demo: StatefulSet, stable names, per-Pod storage, per-Pod DNS

```console
$ kubectl apply -f manifests/03-statefulset.yaml
service/db created
statefulset.apps/db created

$ kubectl get pods,pvc -l app=db
NAME       READY   STATUS    RESTARTS   AGE
pod/db-0   1/1     Running   0          8s
pod/db-1   1/1     Running   0          4s

$ kubectl get pvc
NAME        STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS
data-db-0   Bound    pvc-574d697f-491b-4082-85a4-685778abcae7   64Mi       RWO            standard
data-db-1   Bound    pvc-cc303650-ede0-43d6-92b5-5b0bb3d226c8   64Mi       RWO            standard
```

`db-0` is 8 s old and `db-1` is 4 s old: they were created in order. Each has
its own PVC, named after it. Each Pod wrote its identity to its volume on first
start:

```console
$ kubectl exec db-0 -- cat /data/id
created by db-0 at 13:30:54

$ kubectl get pod db-0 -o jsonpath='{.metadata.name} IP={.status.podIP}'
db-0 IP=10.244.0.27

$ kubectl delete pod db-0
pod "db-0" deleted from s11-compare namespace

$ kubectl get pod db-0 -o jsonpath='{.metadata.name} IP={.status.podIP}'
db-0 IP=10.244.0.34

$ kubectl exec db-0 -- cat /data/id
created by db-0 at 13:30:54
```

The replacement has the **same name and the same data**, but a **new IP**. It
re-attached `data-db-0` and found the file the first `db-0` wrote. A Deployment
Pod would have come back with a random new name and no link to any particular
volume.

DNS through the headless Service tracks the new IP:

```console
$ kubectl exec dnsclient -- dig +short db-0.db.s11-compare.svc.cluster.local
10.244.0.34
$ kubectl exec dnsclient -- dig +short db-1.db.s11-compare.svc.cluster.local
10.244.0.29
$ kubectl exec dnsclient -- dig +short db.s11-compare.svc.cluster.local
10.244.0.34
10.244.0.29
```

Scale-down removes the highest ordinal, and **its PVC is kept**:

```console
$ kubectl scale sts/db --replicas=1
$ kubectl get pods,pvc -l app=db
NAME       READY   STATUS        RESTARTS   AGE
pod/db-0   1/1     Running       0          6s
pod/db-1   1/1     Terminating   0          41s

$ kubectl get pvc
NAME        STATUS   VOLUME                                     CAPACITY
data-db-0   Bound    pvc-574d697f-491b-4082-85a4-685778abcae7   64Mi
data-db-1   Bound    pvc-cc303650-ede0-43d6-92b5-5b0bb3d226c8   64Mi
```

`data-db-1` stays `Bound` after `db-1` is gone. Scaling back up to 2 would
re-attach it to the new `db-1` (not shown here). Kubernetes does not delete database volumes on
scale-down unless you ask it to.

---

## 3. ReplicaSet vs Service

| | ReplicaSet | Service |
|---|---|---|
| **Responsibility** | **How many** Pods exist. Creates replacements when Pods die | **How to reach** them. One stable virtual IP + DNS name in front of whatever Pods match a selector |
| **Talks to** | The API server (creates/deletes Pod objects) | Nothing at runtime. kube-proxy programs iptables/IPVS rules from its EndpointSlices |
| **Knows about the other?** | No | No. Both only share a **label selector** (`app: backend`) |
| **Changes when Pods are replaced** | Its Pod list | Its EndpointSlice (updated automatically); its ClusterIP never changes |

**Why a Service is required:** a ReplicaSet keeps Pods alive by *replacing*
them, and every replacement gets a new IP. Without a Service, clients would
have to find Pod IPs themselves and notice whenever they change. The Service
is the fixed address; the ReplicaSet keeps Pods existing behind it.

**How traffic reaches Pods:** client → DNS `backend-svc` → ClusterIP
`10.96.41.147` → kube-proxy's rules on the node (DNAT) → one of the Pod IPs in
the EndpointSlice → container port 80.

### Demo: Pod replaced, Service follows automatically

```console
$ kubectl apply -f manifests/04-replicaset-service.yaml
replicaset.apps/backend-rs created
service/backend-svc created

$ kubectl get pods -l app=backend -o wide
NAME               READY   STATUS    RESTARTS   AGE   IP
backend-rs-6sv4z   1/1     Running   0          0s    10.244.0.36
backend-rs-86svq   1/1     Running   0          0s    10.244.0.37

$ kubectl get endpointslices -l kubernetes.io/service-name=backend-svc
NAME                ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
backend-svc-gb9th   IPv4          80      10.244.0.36,10.244.0.37   0s

$ kubectl delete pod backend-rs-6sv4z          # the ReplicaSet's job: replace it
pod "backend-rs-6sv4z" deleted from s11-compare namespace

$ kubectl get pods -l app=backend -o wide
NAME               READY   STATUS    RESTARTS   AGE   IP
backend-rs-86svq   1/1     Running   0          1s    10.244.0.37
backend-rs-vcs2c   1/1     Running   0          1s    10.244.0.38

$ kubectl get endpointslices -l kubernetes.io/service-name=backend-svc   # the Service's job: follow it
NAME                ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
backend-svc-gb9th   IPv4          80      10.244.0.37,10.244.0.38   1s

$ kubectl exec dnsclient -- sh -c 'for i in 1 2 3; do curl -s -o /dev/null -w "%{http_code} via %{remote_ip}\n" http://backend-svc; done'
200 via 10.96.41.147
200 via 10.96.41.147
200 via 10.96.41.147

$ kubectl get svc backend-svc -o jsonpath='selector={.spec.selector} ownerReferences={.metadata.ownerReferences}'
selector={"app":"backend"} ownerReferences=
```

- The ReplicaSet replaced `.36` with `.38`. That is all it does.
- The EndpointSlice changed from `.36,.37` to `.37,.38` without anyone touching
  the Service.
- The client always connects to the same ClusterIP, `10.96.41.147`, and never
  sees a Pod IP.
- The Service has **no ownerReferences** to the ReplicaSet. The only link
  between them is the selector `app: backend`.

---

## Summary

| Comparison | One-line answer |
|---|---|
| Deployment vs ReplicaSet | A ReplicaSet keeps N Pods alive. A Deployment manages ReplicaSets so it can roll out and roll back versions. Use Deployments |
| Deployment vs DaemonSet vs StatefulSet | Interchangeable replicas / one Pod per node / Pods with stable identity and their own storage |
| ReplicaSet vs Service | The ReplicaSet decides how many Pods exist; the Service gives them one stable address. They are linked only by labels |

Cleanup: `kubectl delete namespace s11-compare` (the StatefulSet PVCs go with
the namespace).
