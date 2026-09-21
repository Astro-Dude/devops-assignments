# Kubernetes Services — Homework

Session 11. All five Service types, created and tested on a live cluster, plus
the four ports people confuse in interviews and the DNS behaviour behind each
type.

Command results are **real captured output** from the three-node kind cluster
built in [assignment 08](../08-kubernetes-fundamentals/README.md).

---

## Task 1 — Why Services exist at all

> *"Pods come and go, but Services stay forever."*

The backend for every test below is a 3-replica Deployment
([`manifests/00-backend.yaml`](manifests/00-backend.yaml)) where each pod serves
its own name and IP, so it is always obvious which pod answered:

```bash
$ kubectl get pods -l app=web -o wide
NAME                   READY   STATUS    RESTARTS   AGE   IP            NODE                NOMINATED NODE   READINESS GATES
web-574764bdf8-5rsw2   1/1     Running   0          5s    10.244.1.68   devops-hw-worker    <none>           <none>
web-574764bdf8-7h4wz   1/1     Running   0          5s    10.244.1.69   devops-hw-worker    <none>           <none>
web-574764bdf8-9vm8g   1/1     Running   0          5s    10.244.2.52   devops-hw-worker2   <none>           <none>
```

### The proof, in one experiment

Note the Service's ClusterIP and the three pod IPs, then **delete every pod**:

```bash
$ kubectl get svc web-clusterip -o jsonpath='{.spec.clusterIP}'; echo
10.96.185.130

$ kubectl get pods -l app=web -o jsonpath='{range .items[*]}{.metadata.name} {.status.podIP}{"\n"}{end}'
web-574764bdf8-5rsw2 10.244.1.68
web-574764bdf8-7h4wz 10.244.1.69
web-574764bdf8-9vm8g 10.244.2.52

$ kubectl delete pod -l app=web
pod "web-574764bdf8-5rsw2" deleted from default namespace
pod "web-574764bdf8-7h4wz" deleted from default namespace
pod "web-574764bdf8-9vm8g" deleted from default namespace
```

After the Deployment replaces them:

```bash
$ kubectl get pods -l app=web -o jsonpath='{range .items[*]}{.metadata.name} {.status.podIP}{"\n"}{end}'
web-574764bdf8-6xt8c 10.244.2.54
web-574764bdf8-r49vz 10.244.1.71
web-574764bdf8-stl4j 10.244.2.53

$ kubectl get svc web-clusterip -o jsonpath='{.spec.clusterIP}'; echo
10.96.185.130

$ kubectl exec client -- curl -s http://web-clusterip:8080
served by web-574764bdf8-r49vz at 10.244.1.71
```

**Every pod name changed. Every pod IP changed. The ClusterIP did not, and the
request still worked.** That is the entire job of a Service. Anything that had
hard-coded `10.244.1.68` is now broken; anything using `web-clusterip` never
noticed.

---

## Task 2 — The four ports you must never confuse

This trips people up because three of the four are called "port" and they belong
to different objects. From the real NodePort Service and its backing pod:

```bash
$ kubectl get svc web-nodeport -o jsonpath='{.spec.ports[0]}'; echo
{"name":"http","nodePort":30080,"port":8080,"protocol":"TCP","targetPort":80}

$ kubectl get deploy web -o jsonpath='{.spec.template.spec.containers[0].ports[0]}'; echo
{"containerPort":80,"name":"http","protocol":"TCP"}
```

```
   OUTSIDE                  NODE                  SERVICE                POD
  the cluster
                    ┌──────────────────┐
  client ─────────► │  nodePort 30080  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────────────────┐
                    │  ClusterIP 10.96.138.211     │
                    │  port 8080                   │
                    └────────┬─────────────────────┘
                             │
                    ┌────────▼─────────────────────┐
                    │  targetPort 80               │  ──► containerPort 80
                    │  (matched on the pod)        │      (what nginx listens on)
                    └──────────────────────────────┘
```

| Port | Lives on | Meaning | Value here |
|---|---|---|---|
| `nodePort` | the **Service** | Port opened on *every node's* IP. Range 30000–32767. | 30080 |
| `port` | the **Service** | Port the ClusterIP itself listens on. | 8080 |
| `targetPort` | the **Service** | Where the Service forwards to *on the pod*. | 80 |
| `containerPort` | the **Pod** | Documentation of what the container listens on. | 80 |

Two things worth knowing:

- **`port` and `targetPort` are deliberately different here (8080 vs 80)** to
  show they are independent. Clients say `web-clusterip:8080`; nginx still only
  listens on 80.
- **`containerPort` is almost purely informational.** It does not open, publish
  or restrict anything. `targetPort` is what actually decides where traffic
  goes — which is why the mismatch demonstrated in Task 8 breaks silently.

---

## Task 3 — All five types, side by side

```bash
$ kubectl get svc -o wide
NAME            TYPE           CLUSTER-IP      EXTERNAL-IP      PORT(S)          AGE   SELECTOR
external-db     ExternalName   <none>          www.google.com   <none>           21s   <none>
kubernetes      ClusterIP      10.96.0.1       <none>           443/TCP          41m   <none>
web-clusterip   ClusterIP      10.96.185.130   <none>           8080/TCP         21s   app=web
web-headless    ClusterIP      None            <none>           80/TCP           21s   app=web
web-lb          LoadBalancer   10.96.214.83    172.19.255.201   80:31716/TCP     21s   app=web
web-nodeport    NodePort       10.96.138.211   <none>           8080:30080/TCP   21s   app=web
```

Everything you need to tell them apart is in that one listing:

| | CLUSTER-IP | EXTERNAL-IP | Reachable from |
|---|---|---|---|
| **ClusterIP** | a virtual IP | none | inside the cluster only |
| **NodePort** | a virtual IP | none | inside, **+ every node IP:30080** |
| **LoadBalancer** | a virtual IP | **`172.19.255.201`** | inside, every node, **+ one external IP** |
| **ExternalName** | **`<none>`** | a DNS name | it is DNS only — nothing is proxied |
| **Headless** | **`None`** | none | inside, but DNS returns **pod IPs** |

### A note on the LoadBalancer

kind is a bare-metal cluster with no cloud provider, so a `LoadBalancer` Service
would normally sit at `EXTERNAL-IP: <pending>` forever — there is nothing to
answer the request. **MetalLB** was installed to supply that missing piece, with
a pool carved out of the Docker network the nodes already sit on:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: kind-pool
  namespace: metallb-system
spec:
  addresses:
    - 172.19.255.200-172.19.255.250
```

That is why `web-lb` has a genuine external IP below rather than `<pending>`.

---

## Task 4 — ClusterIP (the default)

```yaml
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
    - port: 8080
      targetPort: 80
```

```bash
$ kubectl exec client -- curl -s http://web-clusterip:8080
served by web-574764bdf8-9vm8g at 10.244.2.52

$ kubectl exec client -- curl -s http://web-clusterip:8080
served by web-574764bdf8-5rsw2 at 10.244.1.68

$ kubectl exec client -- curl -s http://web-clusterip:8080
served by web-574764bdf8-9vm8g at 10.244.2.52
```

Different pods answer consecutive requests — that is kube-proxy load-balancing.
Over 30 requests:

```bash
$ kubectl exec client -- sh -c 'for i in $(seq 1 30); do curl -s http://web-clusterip:8080; done' | sort | uniq -c
  12 served by web-574764bdf8-5rsw2 at 10.244.1.68
   6 served by web-574764bdf8-7h4wz at 10.244.1.69
  12 served by web-574764bdf8-9vm8g at 10.244.2.52
```

12 / 6 / 12 rather than a clean 10 / 10 / 10. kube-proxy in iptables mode picks a
backend **at random per connection**, not round-robin, so the distribution is
only even in expectation. Worth knowing before anyone reports it as a bug.

### "Internal only" is a real boundary

```bash
$ curl -s --max-time 5 http://10.96.185.130:8080; echo "curl exit=$?"
curl exit=28
```

Exit 28 is *timeout*. From the host, the ClusterIP is unreachable — it is a
virtual IP that exists only as iptables rules inside the cluster's nodes. There
is no process listening on it anywhere; nothing would answer an ARP request for
it.

---

## Task 5 — NodePort

```bash
$ kubectl get svc web-nodeport -o wide
NAME           TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE   SELECTOR
web-nodeport   NodePort   10.96.138.211   <none>        8080:30080/TCP   77s   app=web
```

From the host, through kind's port mapping:

```bash
$ curl -s http://localhost:30080
served by web-574764bdf8-9vm8g at 10.244.2.52
```

### The part that surprises people

A NodePort opens on **every node**, including nodes that are running none of the
pods. Tested against all three node IPs in turn:

```bash
$ curl from inside devops-hw-control-plane -> http://172.19.0.3:30080
served by web-574764bdf8-5rsw2 at 10.244.1.68

$ curl from inside devops-hw-worker -> http://172.19.0.4:30080
served by web-574764bdf8-9vm8g at 10.244.2.52

$ curl from inside devops-hw-worker2 -> http://172.19.0.2:30080
served by web-574764bdf8-7h4wz at 10.244.1.69
```

Look carefully at the **first** line. `devops-hw-control-plane` runs **no `web`
pod at all** — the control-plane taint kept them off it — yet it answered on
30080 and forwarded to a pod on a worker. Every node's kube-proxy knows the full
endpoint list and will route to any of them, which is exactly what lets you point
a dumb external load balancer at *any* node and have it work.

The second detail: each node routed to a *different* pod, including pods on other
nodes. A NodePort does not prefer local pods by default (that behaviour is
`externalTrafficPolicy: Local`, which trades even balancing for preserved client
source IPs).

---

## Task 6 — LoadBalancer

```bash
$ kubectl get svc web-lb -o wide
NAME     TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)        AGE   SELECTOR
web-lb   LoadBalancer   10.96.214.83   172.19.255.201   80:31716/TCP   78s   app=web
```

```bash
$ curl http://172.19.255.201     # from a container on the kind network
served by web-574764bdf8-7h4wz at 10.244.1.69
```

### LoadBalancer is NodePort with something extra bolted on

```bash
$ kubectl get svc web-lb -o jsonpath='{.spec.ports[0]}'; echo
{"name":"http","nodePort":31716,"port":80,"protocol":"TCP","targetPort":80}
```

**`nodePort: 31716` — which nobody asked for.** The manifest only specified
`port: 80` and `targetPort: 80`. Kubernetes allocated a NodePort anyway, because
the three types are strictly cumulative:

```
ClusterIP   ─────►  a virtual IP inside the cluster
    +
NodePort    ─────►  ... plus a port on every node
    +
LoadBalancer─────►  ... plus an external IP pointing at those node ports
```

A LoadBalancer Service **is** a NodePort Service, plus a request to the cloud
provider (here MetalLB) to point something external at it. This is why a
LoadBalancer costs money per service on a cloud provider, and why teams put one
Ingress in front of many services instead — the subject of
[assignment 11](../11-ingress-configmaps-secrets/README.md).

---

## Task 7 — ExternalName

```yaml
spec:
  type: ExternalName
  externalName: www.google.com
```

```bash
$ kubectl get svc external-db -o wide
NAME          TYPE           CLUSTER-IP   EXTERNAL-IP      PORT(S)   AGE   SELECTOR
external-db   ExternalName   <none>       www.google.com   <none>    93s   <none>
```

No cluster IP, no selector, no ports. And, decisively:

```bash
$ kubectl get endpoints external-db
Error from server (NotFound): endpoints "external-db" not found
```

**The Endpoints object does not exist.** The selector-based Services in this exercise get backend endpoints. This
one does not, because **ExternalName does no proxying whatsoever** — it is a
CoreDNS rule and nothing else:

```bash
$ kubectl exec client -- nslookup external-db.default.svc.cluster.local
Server:		10.96.0.10
Address:	10.96.0.10#53

external-db.default.svc.cluster.local	canonical name = www.google.com.
Name:	www.google.com
Address: 142.251.150.119
Name:	www.google.com
Address: 142.251.155.119
Name:	www.google.com
Address: 142.251.154.119
...
```

A **CNAME**, followed by the real external addresses. Traffic goes straight from
the pod to the internet; it never passes through kube-proxy.

The practical use: point `payments-db.default.svc.cluster.local` at a managed
RDS hostname, so application config says `payments-db` in every environment, and
only the Service object differs between dev and prod. The gotcha is that because
it is a CNAME, **TLS certificate validation sees the real hostname**, not the
Service name.

---

## Task 8 — Headless Service

One line makes a Service headless:

```yaml
spec:
  clusterIP: None
```

```bash
$ kubectl get svc web-headless -o wide
NAME           TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE   SELECTOR
web-headless   ClusterIP   None         <none>        80/TCP    93s   app=web
```

The type still says `ClusterIP`; the CLUSTER-IP column says `None`.

### The difference is entirely in DNS

Headless — one A record **per pod**:

```bash
$ kubectl exec client -- nslookup web-headless.default.svc.cluster.local
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	web-headless.default.svc.cluster.local
Address: 10.244.2.52
Name:	web-headless.default.svc.cluster.local
Address: 10.244.1.69
Name:	web-headless.default.svc.cluster.local
Address: 10.244.1.68
```

Normal ClusterIP — **one** virtual IP:

```bash
$ kubectl exec client -- nslookup web-clusterip.default.svc.cluster.local
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	web-clusterip.default.svc.cluster.local
Address: 10.96.185.130
```

Yet both Services have identical backends:

```bash
$ kubectl get endpointslice -o custom-columns='NAME:.metadata.name,SERVICE:.metadata.labels.kubernetes\.io/service-name,ENDPOINTS:.endpoints[*].addresses,PORTS:.ports[*].port'
NAME                  SERVICE         ENDPOINTS                                   PORTS
kubernetes            kubernetes      [172.19.0.3]                                6443
web-clusterip-xbl8v   web-clusterip   [10.244.1.69],[10.244.2.52],[10.244.1.68]   80
web-headless-jzz9z    web-headless    [10.244.1.69],[10.244.2.52],[10.244.1.68]   80
web-lb-hwt6h          web-lb          [10.244.1.68],[10.244.1.69],[10.244.2.52]   80
web-nodeport-2phxb    web-nodeport    [10.244.1.68],[10.244.1.69],[10.244.2.52]   80
```

Same three endpoints for all four selector-based Services. **The difference is
not what they track — it is whether kube-proxy puts a virtual IP in front.**

Headless hands the client the raw list and steps out of the way, which is what
you want when the *client* must choose the backend: a database driver that needs
to send writes to the primary and reads to replicas, or a Kafka client that
connects to specific brokers. It is also what StatefulSets use to give each pod a
stable DNS name — demonstrated in
[assignment 09](../09-k8s-core-objects/README.md).

---

## Task 9 — DNS and FQDNs

Every pod is handed this:

```bash
$ kubectl exec client -- cat /etc/resolv.conf
search default.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

That `search` list is why short names work. All four of these address the same
Service:

```bash
$ kubectl exec client -- sh -c 'curl -s http://web-clusterip:8080 && curl -s http://web-clusterip.default:8080 && curl -s http://web-clusterip.default.svc:8080 && curl -s http://web-clusterip.default.svc.cluster.local:8080'
served by web-574764bdf8-9vm8g at 10.244.2.52
served by web-574764bdf8-9vm8g at 10.244.2.52
served by web-574764bdf8-7h4wz at 10.244.1.69
served by web-574764bdf8-7h4wz at 10.244.1.69
```

The full form is:

```
  web-clusterip  .  default  .  svc  .  cluster.local
  ─────────────     ───────    ───    ─────────────
    service         namespace  type    cluster domain
```

### `ndots:5` is a real performance trap

`ndots:5` means: *if a name has fewer than 5 dots, try every `search` suffix
before trying it as-is.* So a pod looking up `www.google.com` (2 dots) actually
queries:

```
www.google.com.default.svc.cluster.local   -> NXDOMAIN
www.google.com.svc.cluster.local           -> NXDOMAIN
www.google.com.cluster.local               -> NXDOMAIN
www.google.com                             -> finally, the answer
```

Four queries where one would do, for every external hostname a pod resolves.
This is a well-known source of CoreDNS load in busy clusters. The fix is a
trailing dot — `www.google.com.` — which marks the name absolute, or a custom
`dnsConfig` lowering `ndots`.

**A cross-namespace call must use at least `service.namespace`**, because the
first search suffix only covers the pod's own namespace.

---

## Task 10 — Troubleshooting Services

There are two distinct failure modes and they look completely different once you
know where to look.

### Failure A — no endpoints (selector matches nothing)

Covered in [assignment 09](../09-k8s-core-objects/README.md): the Service is
healthy, the pods are healthy, and `ENDPOINTS` is `<none>`. Requests time out.

### Failure B — endpoints exist, but the port is wrong

This one is nastier, because every "is it healthy" check passes:

```bash
$ kubectl get svc broken-tp
NAME        TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
broken-tp   ClusterIP   10.96.151.191   <none>        80/TCP    6s

$ kubectl get endpointslice -l kubernetes.io/service-name=broken-tp -o custom-columns='ENDPOINTS:.endpoints[*].addresses,PORT:.ports[*].port'
ENDPOINTS                                   PORT
[10.244.2.53],[10.244.1.71],[10.244.2.54]   9999
```

**Three healthy endpoints are listed.** A check that only asks "does this
Service have endpoints?" passes cleanly. But:

```bash
$ kubectl exec client -- curl -s --max-time 5 http://broken-tp:80
command terminated with exit code 7
```

Exit code **7 is *connection refused***, not a timeout. nginx listens on 80; the
Service forwards to 9999, where nothing is listening, so the pod's kernel
actively rejects the connection.

That distinction is the diagnostic:

| Symptom | curl exit | Means |
|---|---|---|
| Hangs, then gives up | **28** (timeout) | Packets going nowhere — no endpoints, or a NetworkPolicy dropping them |
| Fails instantly | **7** (refused) | Reached a pod, but nothing is listening on that port — **wrong `targetPort`** |

### The order to check things in

```bash
kubectl get endpoints <svc>       # empty?  -> selector is wrong
kubectl get svc <svc> -o yaml     # targetPort match the containerPort?
kubectl get pods --show-labels    # do the pod labels match the selector exactly?
kubectl exec <client> -- nslookup <svc>   # does the name even resolve?
```

---

## What I took away

- **A Service is a stable name plus a list of IPs, and nothing more.** Deleting
  all three pods changed every pod IP and broke nothing.
- **The types are cumulative, not alternatives.** The LoadBalancer allocated a
  NodePort (31716) that nobody asked for, because it is built on one.
- **ExternalName is not a Service in the same sense as the others** — it has no
  Endpoints object at all, and kube-proxy is never involved.
- **Headless vs ClusterIP is purely a DNS decision.** Identical EndpointSlices;
  the only difference is whether a virtual IP sits in front.
- **kube-proxy balances randomly per connection**, not round-robin — 12/6/12
  over 30 requests, not 10/10/10.
- **curl's exit code diagnoses the Service for you:** 28 means nothing is
  listed, 7 means something is listed on the wrong port.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Understand why Services are needed | Done — deleted all pods, every IP changed, ClusterIP and traffic unaffected |
| 2 | The 4 ports (port / targetPort / nodePort / containerPort) | Done — all four read from live objects, `port` ≠ `targetPort` deliberately |
| 3 | Create a ClusterIP Service | Done — `web-clusterip`, load balancing measured over 30 requests |
| 3 | Show it is internal-only | Done — host `curl` to the ClusterIP times out (exit 28) |
| 4 | Create a NodePort Service | Done — `web-nodeport` on 30080 |
| 4 | Show it answers on every node | Done — all 3 nodes tested, **incl. a node running no pod** |
| 5 | Create a LoadBalancer Service | Done — real `EXTERNAL-IP 172.19.255.201` via MetalLB, not `<pending>` |
| 5 | Show LoadBalancer builds on NodePort | Done — auto-allocated `nodePort: 31716` |
| 6 | Create an ExternalName Service | Done — CNAME resolution captured; **no Endpoints object exists** |
| 7 | Create a Headless Service | Done — DNS returns 3 pod IPs vs 1 virtual IP, identical EndpointSlices |
| 8 | Understand cluster DNS and FQDNs | Done — all 4 name forms tested, `ndots:5` trap explained |
| 9 | Troubleshoot Service problems | Done — wrong-`targetPort` failure built and diagnosed by curl exit code |

## Raw evidence

The [evidence directory](evidence/) preserves the original command transcripts,
including failed attempts and intermediate states. YAML listings are configuration,
and explanatory tables or shortened excerpts summarize those captures.
