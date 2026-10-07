# Kubernetes Fundamentals — Homework

Session 9. Cluster architecture, the control plane, and the first workloads.
Command results below are **real captured output** from a live three-node
Kubernetes v1.37 cluster. The spec asks for **Minikube**, so Minikube was also
installed and the official Kubernetes Basics tutorial was done on it from start
to finish. That is in [Task 6](#task-6--minikube-and-the-official-kubernetes-basics-tutorial).

---

## The cluster used for sessions 9–15

All the Kubernetes homework in this repository runs against one local cluster,
created with **kind** (Kubernetes IN Docker). kind runs each Kubernetes node as
a Docker container, which is what makes a genuinely multi-node cluster possible
on a laptop — and a multi-node cluster matters, because scheduling, DaemonSets
and "why is my pod Pending" are invisible on a single node.

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: devops-hw
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
        protocol: TCP
      - containerPort: 443
        hostPort: 8443
        protocol: TCP
      - containerPort: 30080
        hostPort: 30080
        protocol: TCP
      - containerPort: 30081
        hostPort: 30081
        protocol: TCP
  - role: worker
  - role: worker
```

Two details in that file are there for later sessions:

- **`ingress-ready=true`** labels the control-plane node so the ingress-nginx
  controller will schedule onto it (session 12).
- **`extraPortMappings`** punches host ports through the node container. Ingress
  lands on **8080/8443** rather than 80/443 because port 80 on this machine is
  already taken by an unrelated container — the same collision documented in
  [session 08](../08-docker-network/README.md). NodePort demos use
  **30080/30081**.

```bash
$ kind create cluster --config kind-config.yaml
 • Ensuring node image (kindest/node:v1.37.0) 🖼️  ...
 ✓ Ensuring node image (kindest/node:v1.37.0) 🖼️
 • Preparing nodes 📦 📦 📦   ...
 ✓ Preparing nodes 📦 📦 📦
 • Writing configuration 📜  ...
 ✓ Writing configuration 📜
 • Starting control-plane 🕹️  ...
 ✓ Starting control-plane 🕹️
 • Installing CNI 🔌  ...
 ✓ Installing CNI 🔌
 • Installing StorageClass 💾  ...
 ✓ Installing StorageClass 💾
 • Joining worker nodes 🚜  ...
 ✓ Joining worker nodes 🚜
Set kubectl context to "kind-devops-hw"
```

### Versions

```bash
$ kind version
kind v0.33.0 go1.27.1 darwin/arm64

$ kubectl version
Client Version: v1.36.1
Kustomize Version: v5.8.1
Server Version: v1.37.0
```

---

## Task 1 — Kubernetes architecture

### The picture

```
                        ┌─────────────────────────────────────────────┐
                        │   CONTROL PLANE  (devops-hw-control-plane)  │
                        │                                             │
   kubectl ──────────►  │   kube-apiserver   ◄──►   etcd              │
   (every request       │        ▲                 (the only          │
    goes here)          │        │                  stateful part)    │
                        │        ├──► kube-scheduler                  │
                        │        └──► kube-controller-manager         │
                        └────────────────────┬────────────────────────┘
                                             │  (watch / report status)
                     ┌───────────────────────┼───────────────────────┐
                     │                       │                       │
             ┌───────▼────────┐      ┌───────▼────────┐              │
             │ devops-hw-     │      │ devops-hw-     │              │
             │   worker       │      │   worker2      │              │
             │                │      │                │              │
             │  kubelet       │      │  kubelet       │              │
             │  kube-proxy    │      │  kube-proxy    │              │
             │  containerd    │      │  containerd    │              │
             │                │      │                │              │
             │  [ pods ]      │      │  [ pods ]      │              │
             └────────────────┘      └────────────────┘              │
                                                                     │
                     kindnet (CNI) gives every pod a routable IP ────┘
```

### The nodes

```bash
$ kubectl get nodes -o wide
NAME                      STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                       KERNEL-VERSION            CONTAINER-RUNTIME
devops-hw-control-plane   Ready    control-plane   96s   v1.37.0   172.19.0.3    <none>        Debian GNU/Linux 13 (trixie)   7.0.12-linuxkit (arm64)   containerd://2.3.4
devops-hw-worker          Ready    <none>          86s   v1.37.0   172.19.0.4    <none>        Debian GNU/Linux 13 (trixie)   7.0.12-linuxkit (arm64)   containerd://2.3.4
devops-hw-worker2         Ready    <none>          86s   v1.37.0   172.19.0.2    <none>        Debian GNU/Linux 13 (trixie)   7.0.12-linuxkit (arm64)   containerd://2.3.4
```

The container runtime is **containerd**, not Docker. Docker here is only the
thing running the node containers; inside each node, Kubernetes talks to
containerd through CRI. That the two are unrelated layers is easier to see when
you can watch both:

```bash
$ docker ps --filter name=devops-hw --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
NAMES                     IMAGE                  STATUS
devops-hw-control-plane   kindest/node:v1.37.0   Up About a minute
devops-hw-worker          kindest/node:v1.37.0   Up About a minute
devops-hw-worker2         kindest/node:v1.37.0   Up About a minute
```

### Where the control plane actually lives

```bash
$ kubectl cluster-info
Kubernetes control plane is running at https://127.0.0.1:55599
CoreDNS is running at https://127.0.0.1:55599/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
```

Every control-plane component is itself a pod, in `kube-system`:

```bash
$ kubectl get pods -n kube-system -o wide
NAME                                              READY   STATUS    RESTARTS   AGE   IP           NODE                      NOMINATED NODE   READINESS GATES
coredns-559f6c778d-9fvsj                          1/1     Running   0          87s   10.244.0.2   devops-hw-control-plane   <none>           <none>
coredns-559f6c778d-n4s9v                          1/1     Running   0          87s   10.244.0.4   devops-hw-control-plane   <none>           <none>
etcd-devops-hw-control-plane                      1/1     Running   0          94s   172.19.0.3   devops-hw-control-plane   <none>           <none>
kindnet-2z74l                                     1/1     Running   0          87s   172.19.0.3   devops-hw-control-plane   <none>           <none>
kindnet-l888k                                     1/1     Running   0          86s   172.19.0.4   devops-hw-worker          <none>           <none>
kindnet-shssv                                     1/1     Running   0          86s   172.19.0.2   devops-hw-worker2         <none>           <none>
kube-apiserver-devops-hw-control-plane            1/1     Running   0          94s   172.19.0.3   devops-hw-control-plane   <none>           <none>
kube-controller-manager-devops-hw-control-plane   1/1     Running   0          94s   172.19.0.3   devops-hw-control-plane   <none>           <none>
kube-proxy-4bzhg                                  1/1     Running   0          86s   172.19.0.2   devops-hw-worker2         <none>           <none>
kube-proxy-gn2g8                                  1/1     Running   0          86s   172.19.0.4   devops-hw-worker          <none>           <none>
kube-proxy-mk5dt                                  1/1     Running   0          87s   172.19.0.3   devops-hw-control-plane   <none>           <none>
kube-scheduler-devops-hw-control-plane            1/1     Running   0          94s   172.19.0.3   devops-hw-control-plane   <none>           <none>
metrics-server-84c99cb944-gz46w                   1/1     Running   0          66s   10.244.2.3   devops-hw-worker2         <none>           <none>
```

Reading that list carefully tells you most of the architecture:

| Component | Where | What it does |
|---|---|---|
| `etcd` | control-plane only, **1 replica** | The cluster's only database. Every object you ever create lives here. Lose etcd, lose the cluster. |
| `kube-apiserver` | control-plane only | The **single** front door. `kubectl`, the scheduler, the controllers and every kubelet all talk to this and nothing else. |
| `kube-scheduler` | control-plane only | Watches for pods with no `nodeName` and picks a node for them. It only *decides*; it never starts anything. |
| `kube-controller-manager` | control-plane only | Runs the reconcile loops (Deployment → ReplicaSet → Pod, node health, endpoints…). |
| `kube-proxy` | **one per node** (3) | Programs iptables/IPVS so Service ClusterIPs actually route. |
| `kindnet` | **one per node** (3) | The CNI plugin. Gives every pod an IP on `10.244.0.0/16` and routes between nodes. |
| `coredns` | 2 replicas | Cluster DNS. This is what makes `my-svc.my-ns.svc.cluster.local` resolve. |
| `metrics-server` | 1 replica | Serves `kubectl top` and feeds the HPA. Installed for session 13. |

The ones that are **one per node** are DaemonSets — `kube-proxy` and `kindnet`
are the textbook real-world example of why DaemonSets exist (covered properly in
[session 10](../10-k8s-core-objects/README.md)).

### Health of the control plane

```bash
$ kubectl get componentstatuses
Warning: v1 ComponentStatus is deprecated in v1.19+
NAME                 STATUS    MESSAGE   ERROR
controller-manager   Healthy   ok
scheduler            Healthy   ok
etcd-0               Healthy   ok
```

`ComponentStatus` is deprecated — the modern equivalent is scraping each
component's `/healthz`. It is shown here because it is still what most tutorials
reach for, and knowing it is deprecated is the useful part.

### Proof that these are ordinary containers

```bash
$ docker exec devops-hw-control-plane crictl ps --name kube-apiserver -o table
CONTAINER           IMAGE               CREATED              STATE     NAME             ATTEMPT   POD ID              POD                                      NAMESPACE
6346bdb423e2d       6003d52023b9d       About a minute ago   Running   kube-apiserver   0         ddaf7eebc80b0       kube-apiserver-devops-hw-control-plane   kube-system
```

`crictl` is talking straight to containerd inside the node, below Kubernetes.
The API server is just a process in a container like any other.

### What etcd is actually configured with

```bash
$ kubectl -n kube-system get pod -l component=etcd \
    -o jsonpath='{.items[0].spec.containers[0].command}' | tr ',' '\n' | head -20
["etcd"
"--advertise-client-urls=https://172.19.0.3:2379"
"--cert-file=/etc/kubernetes/pki/etcd/server.crt"
"--client-cert-auth=true"
"--data-dir=/var/lib/etcd"
"--feature-gates=InitialCorruptCheck=true"
"--initial-advertise-peer-urls=https://172.19.0.3:2380"
"--initial-cluster=devops-hw-control-plane=https://172.19.0.3:2380"
"--key-file=/etc/kubernetes/pki/etcd/server.key"
"--listen-client-urls=https://127.0.0.1:2379
https://172.19.0.3:2379"
"--listen-metrics-urls=http://127.0.0.1:2381"
"--listen-peer-urls=https://172.19.0.3:2380"
"--name=devops-hw-control-plane"
"--peer-cert-file=/etc/kubernetes/pki/etcd/peer.crt"
"--peer-client-cert-auth=true"
"--peer-key-file=/etc/kubernetes/pki/etcd/peer.key"
"--peer-trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt"
"--snapshot-count=10000"
"--trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt"
```

Worth noticing: **2379** is the client port, **2380** the peer port, mTLS is on
(`--client-cert-auth=true`), and the data lives in `/var/lib/etcd` — which is
exactly the directory you back up.

---

## Task 2 — The API, and how to explore it without Google

The API server is a REST API and it is self-describing. These two commands
replace a lot of documentation lookups.

```bash
$ kubectl api-resources --namespaced=true -o name | head -25
bindings
configmaps
endpoints
events
limitranges
persistentvolumeclaims
pods
podtemplates
replicationcontrollers
resourcequotas
secrets
serviceaccounts
services
controllerrevisions.apps
daemonsets.apps
deployments.apps
replicasets.apps
statefulsets.apps
localsubjectaccessreviews.authorization.k8s.io
horizontalpodautoscalers.autoscaling
cronjobs.batch
jobs.batch
podcertificaterequests.certificates.k8s.io
leases.coordination.k8s.io
endpointslices.discovery.k8s.io
```

```bash
$ kubectl api-versions | head -20
admissionregistration.k8s.io/v1
apiextensions.k8s.io/v1
apiregistration.k8s.io/v1
apps/v1
authentication.k8s.io/v1
authorization.k8s.io/v1
autoscaling/v1
autoscaling/v2
batch/v1
certificates.k8s.io/v1
coordination.k8s.io/v1
discovery.k8s.io/v1
events.k8s.io/v1
flowcontrol.apiserver.k8s.io/v1
metrics.k8s.io/v1beta1
networking.k8s.io/v1
node.k8s.io/v1
policy/v1
rbac.authorization.k8s.io/v1
resource.k8s.io/v1
```

That listing is where the `apiVersion:` line in every manifest comes from.
`Pod` is in the core group, so it is plain `v1`; `Deployment` is in the `apps`
group, so it is `apps/v1`; `HorizontalPodAutoscaler` has both `autoscaling/v1`
and `autoscaling/v2`, which is why session 13's HPA manifest specifies `v2`.

`kubectl explain` documents any field, offline:

```bash
$ kubectl explain pod.spec.containers --recursive | head -25
KIND:       Pod
VERSION:    v1

FIELD: containers <[]Container>


DESCRIPTION:
    List of containers belonging to the pod. Containers cannot currently be
    added or removed. There must be at least one container in a Pod. Cannot be
    updated.
    A single application container that you want to run within a pod.

FIELDS:
  args	<[]string>
  command	<[]string>
  env	<[]EnvVar>
    name	<string> -required-
    value	<string>
    valueFrom	<EnvVarSource>
      configMapKeyRef	<ConfigMapKeySelector>
        key	<string> -required-
        name	<string>
        optional	<boolean>
      fieldRef	<ObjectFieldSelector>
        apiVersion	<string>
```

---

## Task 3 — The first Pod

[`manifests/first-pod.yaml`](manifests/first-pod.yaml):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hello-pod
  labels:
    app: hello
spec:
  containers:
    - name: hello
      image: nginx:1.27-alpine
      ports:
        - containerPort: 80
```

```bash
$ kubectl apply -f manifests/first-pod.yaml
pod/hello-pod created

$ kubectl get pod hello-pod -o wide
NAME        READY   STATUS              RESTARTS   AGE   IP       NODE                NOMINATED NODE   READINESS GATES
hello-pod   0/1     ContainerCreating   0          0s    <none>   devops-hw-worker2   <none>           <none>
```

Caught mid-flight: the scheduler has **already** assigned the pod to
`devops-hw-worker2`, but there is no IP yet and the container is still being
created. Scheduling happens first and instantly; everything after it is the
kubelet's work.

```bash
$ kubectl wait --for=condition=Ready pod/hello-pod --timeout=120s
pod/hello-pod condition met

$ kubectl get pod hello-pod -o wide
NAME        READY   STATUS    RESTARTS   AGE   IP           NODE                NOMINATED NODE   READINESS GATES
hello-pod   1/1     Running   0          1s    10.244.2.5   devops-hw-worker2   <none>           <none>
```

### Describing it

```bash
$ kubectl describe pod hello-pod | sed -n '1,30p'
Name:             hello-pod
Namespace:        default
Priority:         0
Service Account:  default
Node:             devops-hw-worker2/172.19.0.2
Start Time:       Mon, 21 Sep 2026 14:05:19 +0530
Labels:           app=hello
Annotations:      <none>
Status:           Running
IP:               10.244.2.5
IPs:
  IP:  10.244.2.5
Containers:
  hello:
    Container ID:   containerd://b611f5b9c7aad2253e15d4bb655930bb5ea3d490b085f1bc19ff1d2c507d1322
    Image:          nginx:1.27-alpine
    Image ID:       docker.io/library/nginx@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Mon, 21 Sep 2026 14:05:20 +0530
    Ready:          True
    Restart Count:  0
    Environment:    <none>
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-qn6s7 (ro)
Conditions:
  Type                        Status
  PodReadyToStartContainers   True
  Initialized                 True
```

Two things nobody asked for and Kubernetes added anyway: a **ServiceAccount**
(`default`) and a **projected token mount** at
`/var/run/secrets/kubernetes.io/serviceaccount`. Every pod gets an identity
against the API server whether it wants one or not.

The `Container ID` prefix is `containerd://` — confirming the runtime again.

### The event trail

```bash
$ kubectl describe pod hello-pod | sed -n '/^Events:/,$p'
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  1s    default-scheduler  Successfully assigned default/hello-pod to devops-hw-worker2
  Normal  Pulled     1s    kubelet            spec.containers{hello}: Container image "nginx:1.27-alpine" already present on machine and can be accessed by the pod
  Normal  Created    1s    kubelet            spec.containers{hello}: Container created
  Normal  Started    0s    kubelet            spec.containers{hello}: Container started
```

That is the whole pod startup sequence in four lines, and it names who did what:
`default-scheduler` did exactly one thing (chose a node), and `kubelet` did the
other three. This event list is the single most useful output in Kubernetes
troubleshooting — [session 14](../14-kubernetes-troubleshooting/README.md) is
built almost entirely on reading it.

### Reaching into the container

```bash
$ kubectl exec hello-pod -- nginx -v
nginx version: nginx/1.27.5

$ kubectl exec hello-pod -- curl -s -o /dev/null -w 'HTTP %{http_code}\n' localhost:80
HTTP 200

$ kubectl logs hello-pod --tail=3
2026/09/21 08:35:20 [notice] 1#1: start worker process 48
2026/09/21 08:35:20 [notice] 1#1: start worker process 49
::1 - - [21/Sep/2026:08:35:20 +0000] "GET / HTTP/1.1" 200 615 "-" "curl/8.12.1" "-"
```

The third log line is the `curl` from the command above it, logged by nginx from
inside the pod — request and log, both captured live.

```bash
$ kubectl get pod hello-pod -o jsonpath='{.status.phase} {.status.podIP} {.spec.nodeName}'; echo
Running 10.244.2.5 devops-hw-worker2
```

### Why you should not actually do this

```bash
$ kubectl delete pod hello-pod
pod "hello-pod" deleted from default namespace
```

It is gone, permanently. A bare Pod has nothing watching it. That is the entire
argument for the next section.

---

## Task 4 — Deployment, Service, scaling and self-healing

[`manifests/hello-deployment.yaml`](manifests/hello-deployment.yaml):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-deploy
  labels:
    app: hello-deploy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hello-deploy
  template:
    metadata:
      labels:
        app: hello-deploy
    spec:
      containers:
        - name: hello
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
```

```bash
$ kubectl apply -f manifests/hello-deployment.yaml
deployment.apps/hello-deploy created

$ kubectl rollout status deployment/hello-deploy --timeout=120s
Waiting for deployment "hello-deploy" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "hello-deploy" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "hello-deploy" rollout to finish: 2 of 3 updated replicas are available...
deployment "hello-deploy" successfully rolled out
```

### One command creates three kinds of object

```bash
$ kubectl get deploy,rs,pods -l app=hello-deploy -o wide
NAME                           READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES              SELECTOR
deployment.apps/hello-deploy   3/3     3            3           9s    hello        nginx:1.27-alpine   app=hello-deploy

NAME                                      DESIRED   CURRENT   READY   AGE   CONTAINERS   IMAGES              SELECTOR
replicaset.apps/hello-deploy-699b74b567   3         3         3       9s    hello        nginx:1.27-alpine   app=hello-deploy,pod-template-hash=699b74b567

NAME                                READY   STATUS    RESTARTS   AGE   IP           NODE                NOMINATED NODE   READINESS GATES
pod/hello-deploy-699b74b567-7vn9n   1/1     Running   0          9s    10.244.2.4   devops-hw-worker2   <none>           <none>
pod/hello-deploy-699b74b567-n9z5v   1/1     Running   0          9s    10.244.1.6   devops-hw-worker
pod/hello-deploy-699b74b567-zz884   1/1     Running   0          9s    10.244.1.5   devops-hw-worker
```

The **Deployment → ReplicaSet → Pod** chain, visible in one listing. Note the
ReplicaSet's selector has an extra label the Deployment's does not:
`pod-template-hash=699b74b567`. That hash is derived from the pod template, and
it is the mechanism behind rolling updates — change the template, get a
different hash, get a **new** ReplicaSet. Session 10 uses this directly.

Also note the scheduler put all three pods on the **workers**, none on the
control plane. That is the control-plane taint doing its job.

### Exposing it

[`manifests/hello-service.yaml`](manifests/hello-service.yaml):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-svc
spec:
  type: NodePort
  selector:
    app: hello-deploy
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30080
```

```bash
$ kubectl apply -f manifests/hello-service.yaml
service/hello-svc created

$ kubectl get svc hello-svc -o wide
NAME        TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE   SELECTOR
hello-svc   NodePort   10.96.236.92   <none>        80:30080/TCP   0s    app=hello-deploy

$ kubectl get endpoints hello-svc
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME        ENDPOINTS                                   AGE
hello-svc   10.244.1.5:80,10.244.1.6:80,10.244.2.4:80   0s
```

The three endpoint IPs are exactly the three pod IPs from the listing above. A
Service is **a selector plus a list of IPs it found** — nothing more. When a
Service "doesn't work", this command is the first place to look, because empty
endpoints means the selector matched nothing.

Reached from the host, through the kind port mapping:

```bash
$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost:30080
HTTP 200

$ curl -s http://localhost:30080 | head -5
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
```

### Scaling

```bash
$ kubectl scale deployment hello-deploy --replicas=5
deployment.apps/hello-deploy scaled

$ kubectl rollout status deployment/hello-deploy --timeout=120s
Waiting for deployment "hello-deploy" rollout to finish: 3 of 5 updated replicas are available...
Waiting for deployment "hello-deploy" rollout to finish: 4 of 5 updated replicas are available...
deployment "hello-deploy" successfully rolled out

$ kubectl get pods -l app=hello-deploy -o wide
NAME                            READY   STATUS    RESTARTS   AGE   IP           NODE                NOMINATED NODE   READINESS GATES
hello-deploy-699b74b567-7vn9n   1/1     Running   0          35s   10.244.2.4   devops-hw-worker2   <none>           <none>
hello-deploy-699b74b567-8f9w2   1/1     Running   0          1s    10.244.1.7   devops-hw-worker    <none>           <none>
hello-deploy-699b74b567-9xlw2   1/1     Running   0          1s    10.244.2.6   devops-hw-worker2   <none>           <none>
hello-deploy-699b74b567-n9z5v   1/1     Running   0          35s   10.244.1.6   devops-hw-worker    <none>           <none>
hello-deploy-699b74b567-zz884   1/1     Running   0          35s   10.244.1.5   devops-hw-worker    <none>           <none>
```

Three pods are 35s old, two are 1s old — the existing pods were **not**
restarted. Scaling adds and removes; it does not recreate. Note also that the
same ReplicaSet hash `699b74b567` is on all five: scaling changes the replica
count, not the pod template, so no new ReplicaSet appears.

```bash
$ kubectl scale deployment hello-deploy --replicas=3
deployment.apps/hello-deploy scaled

$ kubectl rollout status deployment/hello-deploy --timeout=120s
deployment "hello-deploy" successfully rolled out
```

### Self-healing

Delete a pod that a Deployment owns, and compare with what happened to the bare
pod earlier:

```bash
$ kubectl delete pod hello-deploy-699b74b567-7vn9n
pod "hello-deploy-699b74b567-7vn9n" deleted from default namespace

$ kubectl get pods -l app=hello-deploy
NAME                            READY   STATUS      RESTARTS   AGE
hello-deploy-699b74b567-2mckq   1/1     Running     0          0s
hello-deploy-699b74b567-8f9w2   0/1     Completed   0          1s
hello-deploy-699b74b567-9xlw2   1/1     Running     0          1s
hello-deploy-699b74b567-zz884   1/1     Running     0          35s
```

Caught **0 seconds** after the delete: the replacement `-2mckq` already exists,
while `-8f9w2` (one of the pods being removed by the scale-down) is still
shutting down as `Completed`. The controller's reconcile loop is not polite
about waiting.

```bash
$ kubectl get pods -l app=hello-deploy
NAME                            READY   STATUS    RESTARTS   AGE
hello-deploy-699b74b567-2mckq   1/1     Running   0          10s
hello-deploy-699b74b567-9xlw2   1/1     Running   0          11s
hello-deploy-699b74b567-zz884   1/1     Running   0          45s
```

Settled at 3/3. **RESTARTS is 0 on the new pod** — this is a replacement, not a
restart. The old pod is gone forever and a brand-new one with a new name and new
IP took its place. That distinction is exactly why Services exist, and it is the
whole subject of [session 11](../11-kubernetes-services/README.md).

---

## Task 5 — Namespaces

```bash
$ kubectl get namespaces
NAME                 STATUS   AGE
default              Active   3m25s
ingress-nginx        Active   3m8s
kube-node-lease      Active   3m25s
kube-public          Active   3m25s
kube-system          Active   3m25s
local-path-storage   Active   3m21s
```

`kube-system` holds the control plane; `local-path-storage` is kind's dynamic
volume provisioner (session 13 uses it); `ingress-nginx` was added for session
12; `kube-node-lease` holds the heartbeat objects each kubelet updates so the
controller manager can tell live nodes from dead ones.

```bash
$ kubectl create namespace demo-ns
namespace/demo-ns created

$ kubectl run ns-demo --image=nginx:1.27-alpine -n demo-ns
pod/ns-demo created

$ kubectl get pods -n demo-ns
NAME      READY   STATUS              RESTARTS   AGE
ns-demo   0/1     ContainerCreating   0          0s

$ kubectl get pods
NAME                            READY   STATUS    RESTARTS   AGE
hello-deploy-699b74b567-2mckq   1/1     Running   0          10s
hello-deploy-699b74b567-9xlw2   1/1     Running   0          11s
hello-deploy-699b74b567-zz884   1/1     Running   0          45s
```

The point of that pair: `ns-demo` **exists**, but the second command does not
show it, because `kubectl get pods` without `-n` means the `default` namespace
only. This is the cause of a large share of "my pod disappeared" confusion.

Deleting the namespace deletes everything inside it:

```bash
$ kubectl delete namespace demo-ns
namespace "demo-ns" deleted
```

---

## Task 6 — Minikube, and the official Kubernetes Basics tutorial

The task list starts with *"Install and configure Minikube"* and ends with
*"Perform the Kubernetes Basics tutorial hands-on"*. Everything above runs on
kind, which I kept for sessions 9–15 because it can run several nodes and map
host ports. Here Minikube was installed and the six
[Kubernetes Basics](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
modules were done on it with the tutorial's own commands and images. Then the
cluster was deleted. Full transcript:
[`evidence/s09-minikube-basics-tutorial.txt`](evidence/s09-minikube-basics-tutorial.txt).

Two adaptations, both forced by running on macOS:

- The tutorial uses `kubectl proxy` and then `curl localhost:8001/...`.
  `kubectl get --raw <same path>` goes through the same API server proxy
  without opening a local port, so I used that.
- With the Docker driver on macOS, the Minikube node IP (`192.168.49.2`) sits
  inside Docker's VM and cannot be reached from the Mac. NodePort requests
  were therefore sent from the node itself with `minikube ssh -- curl`.

### Module 1 — Create a cluster: install, start, verify

```console
$ brew install minikube
$ minikube version
minikube version: v1.39.0
commit: 7a9f6a841470a207de8cf4bafcccee0969d8ba10

$ minikube start -p hw-legacy-minikube --driver=docker --cpus=2 --memory=2200
* [hw-legacy-minikube] minikube v1.39.0 on Darwin 27.0 (arm64)
* Using the docker driver based on user configuration
* Using Docker Desktop driver with root privileges
* Starting "hw-legacy-minikube" primary control-plane node in "hw-legacy-minikube" cluster
* Pulling base image v0.0.51 ...
* Configuring CNI (Container Networking Interface) ...
* Verifying Kubernetes components...
  - Using image gcr.io/k8s-minikube/storage-provisioner:v5
* Enabled addons: storage-provisioner, default-storageclass
* Done! kubectl is now configured to use "hw-legacy-minikube" cluster and "default" namespace by default

$ minikube status
hw-legacy-minikube
type: Control Plane
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured

$ kubectl cluster-info
Kubernetes control plane is running at https://127.0.0.1:60437
CoreDNS is running at https://127.0.0.1:60437/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

$ kubectl get nodes -o wide
NAME                 STATUS   ROLES           AGE     VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION            CONTAINER-RUNTIME
hw-legacy-minikube   Ready    control-plane   4m18s   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   7.0.12-linuxkit (arm64)   containerd://2.3.4

$ kubectl get pods -n kube-system
NAME                                         READY   STATUS    RESTARTS   AGE
coredns-559f6c778d-cfz5t                     1/1     Running   0          4m9s
etcd-hw-legacy-minikube                      1/1     Running   0          4m17s
kindnet-ktwnf                                1/1     Running   0          4m9s
kube-apiserver-hw-legacy-minikube            1/1     Running   0          4m16s
kube-controller-manager-hw-legacy-minikube   1/1     Running   0          4m16s
kube-proxy-6smmt                             1/1     Running   0          4m9s
kube-scheduler-hw-legacy-minikube            1/1     Running   0          4m16s
storage-provisioner                          1/1     Running   0          4m14s
```

`minikube status` checks each layer in turn: the host (a Docker container
here), the kubelet inside it, the API server, and whether kubeconfig points at
it. The `kube-system` pods are the same control-plane components identified on
kind in Task 1. Minikube adds its own `storage-provisioner`, and `minikube addons
list` (in the transcript) shows the optional extras it can turn on: dashboard,
ingress, metrics-server and others. Only `default-storageclass` and
`storage-provisioner` are on by default.

### Module 2 — Deploy an app

```console
$ kubectl create deployment kubernetes-bootcamp --image=gcr.io/google-samples/kubernetes-bootcamp:v1
deployment.apps/kubernetes-bootcamp created

$ kubectl get deployments
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
kubernetes-bootcamp   1/1     1            1           23s

$ kubectl get --raw /version          # tutorial: kubectl proxy + curl localhost:8001/version
{
  "major": "1",
  "minor": "37",
  "gitVersion": "v1.37.0",
  "platform": "linux/arm64"
  ...
}
```

### Module 3 — Explore: pods, logs, exec

```console
$ kubectl get pods
NAME                                   READY   STATUS    RESTARTS   AGE
kubernetes-bootcamp-5cc66bcc9b-fx2n7   1/1     Running   0          2m15s

$ kubectl describe pods
Name:             kubernetes-bootcamp-5cc66bcc9b-fx2n7
Node:             hw-legacy-minikube/192.168.49.2
Labels:           app=kubernetes-bootcamp
                  pod-template-hash=5cc66bcc9b
Status:           Running
IP:               10.244.0.3
Controlled By:  ReplicaSet/kubernetes-bootcamp-5cc66bcc9b
    Image:          gcr.io/google-samples/kubernetes-bootcamp:v1
...

$ kubectl get --raw /api/v1/namespaces/default/pods/$POD_NAME:8080/proxy/
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1

$ kubectl logs $POD_NAME
Kubernetes Bootcamp App Started At: 2026-10-07T13:25:47.635Z | Running On:  kubernetes-bootcamp-5cc66bcc9b-fx2n7 
Running On: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | Total Requests: 1 | App Uptime: 112.502 seconds | Log Time: 2026-10-07T13:27:40.138Z

$ kubectl exec $POD_NAME -- env          (excerpt)
HOSTNAME=kubernetes-bootcamp-5cc66bcc9b-fx2n7
NODE_VERSION=6.3.1
KUBERNETES_SERVICE_HOST=10.96.0.1
KUBERNETES_SERVICE_PORT=443

$ kubectl exec $POD_NAME -- cat server.js | head -20
var http = require('http');
var requests=0;
var podname= process.env.HOSTNAME;
...

$ kubectl exec $POD_NAME -- curl -s http://localhost:8080
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
```

The request sent through the API proxy appears in the pod's own log
(`Total Requests: 1`). That shows the `--raw` call really reached the
container.

### Module 4 — Expose with a Service, and use labels

```console
$ kubectl expose deployment/kubernetes-bootcamp --type=NodePort --port 8080
service/kubernetes-bootcamp exposed

$ kubectl get services -l app=kubernetes-bootcamp
NAME                  TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
kubernetes-bootcamp   NodePort   10.96.147.73   <none>        8080:32733/TCP   5s

$ minikube ssh -- curl -s http://192.168.49.2:32733
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1

$ kubectl label pods $POD_NAME version=v1
pod/kubernetes-bootcamp-5cc66bcc9b-fx2n7 labeled

$ kubectl get pods -l version=v1
NAME                                   READY   STATUS    RESTARTS   AGE
kubernetes-bootcamp-5cc66bcc9b-fx2n7   1/1     Running   0          2m17s

$ kubectl delete service -l app=kubernetes-bootcamp
service "kubernetes-bootcamp" deleted from default namespace

$ minikube ssh -- curl -s -m 3 http://192.168.49.2:32733; echo exit=$?
ssh: Process exited with status 7
exit=1

$ kubectl exec $POD_NAME -- curl -s http://localhost:8080
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
```

After the Service is deleted, the NodePort refuses connections (curl exit 7),
but the app inside the pod still answers. The Service was only the way in.
Labels select everything here: `get -l`, `delete -l` and the Service's own
selector. The first NodePort curl in the transcript, sent 0 s after `expose`,
also got exit 7 because kube-proxy had not set up the port yet. Retrying 5 s
later worked.

### Module 5 — Scale

```console
$ kubectl scale deployments/kubernetes-bootcamp --replicas=4
deployment.apps/kubernetes-bootcamp scaled

$ kubectl get pods -o wide
NAME                                   READY   STATUS    RESTARTS   AGE     IP           NODE
kubernetes-bootcamp-5cc66bcc9b-fx2n7   1/1     Running   0          2m49s   10.244.0.3   hw-legacy-minikube
kubernetes-bootcamp-5cc66bcc9b-jk2bq   1/1     Running   0          1s      10.244.0.6   hw-legacy-minikube
kubernetes-bootcamp-5cc66bcc9b-nscdp   1/1     Running   0          1s      10.244.0.5   hw-legacy-minikube
kubernetes-bootcamp-5cc66bcc9b-vxhl4   1/1     Running   0          1s      10.244.0.4   hw-legacy-minikube

$ kubectl describe services/kubernetes-bootcamp | grep -E 'NodePort|Endpoints'
NodePort:                 <unset>  31284/TCP
Endpoints:                10.244.0.3:8080,10.244.0.6:8080,10.244.0.5:8080 + 1 more...

$ for i in $(seq 1 10); do minikube ssh -- curl -s http://192.168.49.2:31284; done
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-jk2bq | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-nscdp | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-vxhl4 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-jk2bq | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-fx2n7 | v=1
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5cc66bcc9b-vxhl4 | v=1

$ kubectl scale deployments/kubernetes-bootcamp --replicas=2
deployment.apps/kubernetes-bootcamp scaled
```

All four pods served requests through one NodePort. The Service's endpoint
list grew to four as soon as the new pods were Ready, with nothing reconfigured.

### Module 6 — Rolling update, a broken update, and rollback

```console
$ kubectl set image deployments/kubernetes-bootcamp kubernetes-bootcamp=docker.io/jocatalin/kubernetes-bootcamp:v2
deployment.apps/kubernetes-bootcamp image updated

$ kubectl rollout status deployments/kubernetes-bootcamp --timeout=180s
Waiting for deployment "kubernetes-bootcamp" rollout to finish: 1 out of 2 new replicas have been updated...
Waiting for deployment "kubernetes-bootcamp" rollout to finish: 1 old replicas are pending termination...
deployment "kubernetes-bootcamp" successfully rolled out

$ for i in 1 2 3 4; do minikube ssh -- curl -s http://192.168.49.2:31284; done
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5b97597885-7hq86 | v=2
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5b97597885-7hq86 | v=2
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5b97597885-vz5v7 | v=2
Hello Kubernetes bootcamp! | Running on: kubernetes-bootcamp-5b97597885-7hq86 | v=2

$ kubectl set image deployments/kubernetes-bootcamp kubernetes-bootcamp=gcr.io/google-samples/kubernetes-bootcamp:v10
deployment.apps/kubernetes-bootcamp image updated

$ kubectl get deployments
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
kubernetes-bootcamp   2/2     1            2           3m35s

$ kubectl get pods          (two old v1 pods still Terminating omitted)
NAME                                   READY   STATUS             RESTARTS   AGE
kubernetes-bootcamp-556487b4d4-mmlgv   0/1     ImagePullBackOff   0          26s
kubernetes-bootcamp-5b97597885-7hq86   1/1     Running            0          30s
kubernetes-bootcamp-5b97597885-vz5v7   1/1     Running            0          39s

$ kubectl rollout undo deployments/kubernetes-bootcamp
deployment.apps/kubernetes-bootcamp rolled back

$ kubectl describe pods | grep -E '^Name:|Image:'      (pods still Terminating omitted)
Name:             kubernetes-bootcamp-5b97597885-7hq86
    Image:          docker.io/jocatalin/kubernetes-bootcamp:v2
Name:             kubernetes-bootcamp-5b97597885-vz5v7
    Image:          docker.io/jocatalin/kubernetes-bootcamp:v2

$ kubectl rollout history deployment/kubernetes-bootcamp
REVISION  CHANGE-CAUSE
1         <none>
3         <none>
4         <none>

$ kubectl delete deployments/kubernetes-bootcamp services/kubernetes-bootcamp
$ minikube stop -p hw-legacy-minikube
* 1 node stopped.
$ minikube delete -p hw-legacy-minikube
* Removed all traces of the "hw-legacy-minikube" cluster.
```

During the broken `v10` rollout the Deployment showed **`2/2` READY,
`1` UP-TO-DATE**. The rolling update created one new pod, saw it stuck in
`ImagePullBackOff`, and never removed the two healthy `v2` pods. Users saw no
outage. `rollout undo` went back to the `v2` ReplicaSet (`5b97597885`). Revision
2 disappears from the history and comes back as revision 4, because an undo is
recorded as a new revision. Session 10 looks at that numbering in detail.

### Minikube vs kind, as used here

| | Minikube (this task) | kind (sessions 9–15) |
|---|---|---|
| Node | 1 Docker container (`hw-legacy-minikube`) | 1–3 Docker containers |
| Extras | `minikube addons` (dashboard, ingress, metrics-server, …) | install manifests yourself |
| Reaching NodePorts from macOS | `minikube service --url` tunnel, or `minikube ssh` | `extraPortMappings` in the config file |
| Multi-node | possible (`--nodes`) but less common | the main reason it was chosen |

---

## What I took away

- **The API server is the only thing anything talks to.** Not the scheduler, not
  the kubelets, not etcd. Everything is a client of one REST API, which is why
  `kubectl` can do everything and why RBAC on that one server is sufficient.
- **Controllers reconcile; they do not execute.** `kubectl scale` writes a number
  to etcd and returns. A control loop notices the difference between 3 and 5 and
  closes the gap. Nothing in the path is a remote procedure call to a node.
- **A Pod is disposable and a Deployment is not.** The deleted bare pod stayed
  deleted; the deleted managed pod was replaced within a second, under a new name
  and a new IP.
- **Pod IPs are not addresses you can hold on to.** Every self-heal changes them.
  Services exist entirely to paper over that.
- `kubectl get endpoints` and `kubectl describe … | sed -n '/^Events:/,$p'` are
  the two commands that answer most "why is this broken" questions.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Set up a working Kubernetes cluster | Done — 3-node kind cluster, v1.37.0 |
| 1 | Understand cluster architecture | Done — every control-plane and node component identified in live output |
| 1 | Control plane vs node components | Done — table mapped to real `kube-system` pods |
| 1 | Verify control-plane health | Done — `componentstatuses`, plus `crictl` at the runtime layer |
| 2 | Understand the Kubernetes API | Done — `api-resources`, `api-versions`, `explain` |
| 3 | Create a Pod | Done — `hello-pod`, Running with IP `10.244.2.5` |
| 3 | Inspect it (describe / logs / exec) | Done — including a live request visible in the pod's own logs |
| 3 | Read the event trail | Done — all four startup events, attributed to scheduler vs kubelet |
| 4 | Create a Deployment | Done — `hello-deploy`, 3/3 ready |
| 4 | Expose it with a Service | Done — NodePort 30080, HTTP 200 from the host |
| 4 | Scale the Deployment | Done — 3 → 5 → 3, proven not to restart existing pods |
| 4 | Demonstrate self-healing | Done — replacement pod caught at age 0s, RESTARTS 0 |
| 5 | Work with namespaces | Done — created, scoped a pod, showed the default-namespace trap, deleted |
| 6 | Install and configure **Minikube** | Done — Minikube v1.39.0, Docker driver, `minikube status` all Running, node Ready |
| 6 | Perform the Kubernetes Basics tutorial hands-on | Done — all 6 modules (create, deploy, explore, expose + labels, scale, update + rollback) with the tutorial's images |

## Raw evidence

The [evidence directory](evidence/) preserves the original command transcripts,
including failed attempts and intermediate states. YAML listings are configuration,
and explanatory tables or shortened excerpts summarize those captures.
