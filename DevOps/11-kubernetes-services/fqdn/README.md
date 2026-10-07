# FQDN — Fully Qualified Domain Names in Kubernetes

Session 11, Task 3. What an FQDN is, how Kubernetes names Services and Pods in
DNS, how namespaces change name lookup, and how a Pod reaches a Service.

All output is **real captured output** from the single-node kind cluster
`hw-legacy` (Kubernetes v1.37, CoreDNS 1.14.6). The lab
([`dns-lab.yaml`](dns-lab.yaml), [`client.yaml`](client.yaml)) creates the same
Service name `api` in **two namespaces**, `s11-dns-a` and `s11-dns-b`. Each
answers with its own namespace name, so every response shows which one you
reached. The namespace also gets a headless Service with a 2-Pod StatefulSet.
Full transcript:
[`../evidence/s11-fqdn-lab.txt`](../evidence/s11-fqdn-lab.txt). The main
README's [Task 9 — DNS and FQDNs](../README.md#task-9--dns-and-fqdns) covers
the same ideas for the `default` namespace.

```bash
kubectl create namespace s11-dns-a
kubectl create namespace s11-dns-b
NS=s11-dns-a envsubst < dns-lab.yaml | kubectl apply -f -
NS=s11-dns-b envsubst < dns-lab.yaml | kubectl apply -f -
kubectl apply -f client.yaml        # nicolaka/netshoot (dig, nslookup, curl) in s11-dns-a
```

---

## 1. What is an FQDN?

A **Fully Qualified Domain Name** is a name that spells out every label up to
the DNS root, so it can only mean one thing anywhere. `www.example.com.` is
fully qualified; the trailing dot is the root. `www` on its own is a *relative*
name. The resolver has to guess the rest from a **search list**.

In Kubernetes the cluster has its own DNS zone, by default `cluster.local`.
Every Service, and optionally every Pod, gets a name in it.

---

## 2. Kubernetes Service DNS and the naming convention

```
  api   .  s11-dns-a  .  svc  .  cluster.local  .
  ───      ─────────     ───     ─────────────
service    namespace    kind    cluster domain    root
```

| Record | Name | Answer |
|---|---|---|
| ClusterIP Service (A) | `<svc>.<ns>.svc.cluster.local` | the Service's ClusterIP |
| Headless Service (A) | `<svc>.<ns>.svc.cluster.local` | **every ready Pod IP** |
| StatefulSet Pod behind headless Service (A) | `<pod>.<svc>.<ns>.svc.cluster.local` | that Pod's IP |
| Any Pod (A) | `<pod-ip-with-dashes>.<ns>.pod.cluster.local` | that IP |
| Named Service port (SRV) | `_<port-name>._<proto>.<svc>.<ns>.svc.cluster.local` | port + target host |
| ExternalName Service (CNAME) | `<svc>.<ns>.svc.cluster.local` | the external hostname |

```console
$ kubectl get svc -n s11-dns-a
NAME           TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
api            ClusterIP   10.96.98.48   <none>        80/TCP    2s
web-headless   ClusterIP   None          <none>        80/TCP    2s

$ kubectl get svc -n s11-dns-b
NAME           TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
api            ClusterIP   10.96.7.141   <none>        80/TCP    1s
web-headless   ClusterIP   None          <none>        80/TCP    1s
```

Two Services are both called `api`, with different ClusterIPs. Only the
namespace part of the FQDN tells them apart.

---

## 3. Why short names work: the Pod's resolver config

The kubelet writes this into every Pod with the default `dnsPolicy:
ClusterFirst`:

```console
$ kubectl -n s11-dns-a exec client -- cat /etc/resolv.conf
search s11-dns-a.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

- `nameserver 10.96.0.10` is the `kube-dns` Service, which is CoreDNS (see
  [`../coredns/README.md`](../coredns/README.md)).
- The **first search domain is the Pod's own namespace**, so the Pod's
  namespace is filled in for short names.
- `ndots:5`: any name with fewer than 5 dots is tried with each search suffix
  before being tried as-is.

From a Pod in `s11-dns-b` the first search domain is different:

```console
$ kubectl -n s11-dns-b exec client-b -- cat /etc/resolv.conf
search s11-dns-b.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

---

## 4. Namespace-based DNS: one short name, two answers

From the client in **`s11-dns-a`**, every form of the name:

```console
$ kubectl -n s11-dns-a exec client -- curl -s http://api
api answering from namespace s11-dns-a
$ kubectl -n s11-dns-a exec client -- curl -s http://api.s11-dns-a
api answering from namespace s11-dns-a
$ kubectl -n s11-dns-a exec client -- curl -s http://api.s11-dns-a.svc
api answering from namespace s11-dns-a
$ kubectl -n s11-dns-a exec client -- curl -s http://api.s11-dns-a.svc.cluster.local
api answering from namespace s11-dns-a
$ kubectl -n s11-dns-a exec client -- curl -s http://api.s11-dns-b
api answering from namespace s11-dns-b
$ kubectl -n s11-dns-a exec client -- curl -s http://api.s11-dns-b.svc.cluster.local
api answering from namespace s11-dns-b
```

From a client in **`s11-dns-b`**, the *same* short name reaches the other Service:

```console
$ kubectl -n s11-dns-b exec client-b -- wget -q -O- http://api
api answering from namespace s11-dns-b
$ kubectl -n s11-dns-b exec client-b -- wget -q -O- http://api.s11-dns-a
api answering from namespace s11-dns-a
```

`nslookup` shows the name the search list actually produced:

```console
$ kubectl -n s11-dns-a exec client -- nslookup api
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	api.s11-dns-a.svc.cluster.local
Address: 10.96.98.48

$ kubectl -n s11-dns-a exec client -- nslookup api.s11-dns-b
Name:	api.s11-dns-b.svc.cluster.local
Address: 10.96.7.141
```

`api.s11-dns-b` has one dot, so the resolver appended the search suffixes. The
second suffix, `svc.cluster.local`, produced `api.s11-dns-b.svc.cluster.local`,
which exists.

**Rule:** the short name `api` only finds a Service in **your own namespace**.
To reach another namespace you need at least `<svc>.<ns>`. The full FQDN works
from anywhere.

### When the other namespace's Service does not exist

```console
$ kubectl -n s11-dns-b delete deploy,svc api
$ kubectl -n s11-dns-a exec client -- curl -s --max-time 3 http://api.s11-dns-b
command terminated with exit code 6
$ kubectl -n s11-dns-a exec client -- nslookup api.s11-dns-b
** server can't find api.s11-dns-b: NXDOMAIN
```

curl exit code **6** means "could not resolve host". DNS returned NXDOMAIN, so
no connection was even attempted. After recreating it:

```console
$ kubectl -n s11-dns-a exec client -- dig +noall +answer api.s11-dns-a.svc.cluster.local api.s11-dns-b.svc.cluster.local
api.s11-dns-a.svc.cluster.local. 30 IN	A	10.96.98.48
api.s11-dns-b.svc.cluster.local. 30 IN	A	10.96.56.203
```

The recreated `api` in `s11-dns-b` has a **new ClusterIP** (`10.96.7.141` →
`10.96.56.203`). Clients that use the name never notice. That is why you
connect by name and never hard-code a ClusterIP.

---

## 5. Pod-to-Service communication, step by step

```
client Pod (s11-dns-a)
  │ 1. app asks for "api"
  │ 2. resolver adds the first search suffix -> api.s11-dns-a.svc.cluster.local
  ▼
CoreDNS (10.96.0.10)  ── 3. answers from its watch of Services: A 10.96.98.48
  │
  ▼
client connects to 10.96.98.48:80
  │ 4. kube-proxy rules on the node DNAT the ClusterIP to a Pod IP from the
  │    Service's EndpointSlice, and port 80 to targetPort "http" (8080)
  ▼
api Pod 10.244.0.41:8080
```

DNS only gives back the stable virtual IP. Picking an actual Pod happens
afterwards, in kube-proxy's rules.

---

## 6. SRV records for named ports

The Service port is named `http`, so CoreDNS also publishes an SRV record
giving the **port number**:

```console
$ kubectl -n s11-dns-a exec client -- dig +noall +answer SRV _http._tcp.api.s11-dns-a.svc.cluster.local
_http._tcp.api.s11-dns-a.svc.cluster.local. 30 IN SRV 0 100 80 api.s11-dns-a.svc.cluster.local.
```

Priority 0, weight 100, **port 80**, target the Service's own A record. Clients
that understand SRV can discover the port instead of hard-coding it.

---

## 7. FQDNs for Pods

### Every Pod: `<ip-with-dashes>.<ns>.pod.cluster.local`

```console
$ kubectl -n s11-dns-a get pod -l app=api -o jsonpath='{.items[0].metadata.name} {.items[0].status.podIP}'
api-77dd6559bc-vsmp4 10.244.0.41

$ kubectl -n s11-dns-a exec client -- dig +noall +answer 10-244-0-41.s11-dns-a.pod.cluster.local
10-244-0-41.s11-dns-a.pod.cluster.local. 30 IN A 10.244.0.41

$ kubectl -n s11-dns-a exec client -- dig +noall +answer -x 10.244.0.41
41.0.244.10.in-addr.arpa. 30	IN	PTR	10-244-0-41.api.s11-dns-a.svc.cluster.local.
```

This record works (`pods insecure` in the Corefile), but it contains the IP, so
you already need the address to build the name. It is only useful for things
like TLS certificates. The reverse (PTR) lookup returns the Pod under its
Service, which is a nice touch.

### StatefulSet Pods behind a headless Service: stable per-Pod names

```console
$ kubectl -n s11-dns-a get pods -l app=web-sts -o wide
NAME    READY   STATUS    RESTARTS   AGE   IP
web-0   1/1     Running   0          3s    10.244.0.42
web-1   1/1     Running   0          3s    10.244.0.47

$ kubectl -n s11-dns-a exec client -- dig +noall +answer web-headless.s11-dns-a.svc.cluster.local
web-headless.s11-dns-a.svc.cluster.local. 30 IN	A 10.244.0.47
web-headless.s11-dns-a.svc.cluster.local. 30 IN	A 10.244.0.42

$ kubectl -n s11-dns-a exec client -- dig +noall +answer web-0.web-headless.s11-dns-a.svc.cluster.local
web-0.web-headless.s11-dns-a.svc.cluster.local.	30 IN A	10.244.0.42

$ kubectl -n s11-dns-a exec client -- dig +noall +answer web-1.web-headless.s11-dns-a.svc.cluster.local
web-1.web-headless.s11-dns-a.svc.cluster.local.	30 IN A	10.244.0.47

$ kubectl -n s11-dns-a exec web-0 -- hostname -f
web-0.web-headless.s11-dns-a.svc.cluster.local
```

The headless Service name returns **both** Pod IPs (no ClusterIP in front).
Each StatefulSet Pod has its own name, and the Pod itself reports it as its
FQDN. Database replicas use these names to find each other; for example, a
replica is pointed at `web-0.web-headless...` as the primary.

---

## 8. Examples of Kubernetes FQDNs

| FQDN | What it is |
|---|---|
| `kubernetes.default.svc.cluster.local` | the API server's Service |
| `kube-dns.kube-system.svc.cluster.local` | CoreDNS itself (10.96.0.10) |
| `api.s11-dns-a.svc.cluster.local` | ClusterIP Service `api` in `s11-dns-a` |
| `api.s11-dns-b.svc.cluster.local` | a different Service with the same name |
| `web-headless.s11-dns-a.svc.cluster.local` | headless Service: all Pod IPs |
| `web-0.web-headless.s11-dns-a.svc.cluster.local` | StatefulSet Pod `web-0` |
| `10-244-0-41.s11-dns-a.pod.cluster.local` | Pod with IP 10.244.0.41 |
| `_http._tcp.api.s11-dns-a.svc.cluster.local` | SRV record for named port `http` |
| `ingress-nginx-controller.ingress-nginx.svc.cluster.local` | a Service in another namespace, used by its FQDN |

## Takeaways

- **Short name = your own namespace only.** Cross-namespace calls need at least
  `<svc>.<ns>`. In config files, write the full FQDN so it works from any
  namespace.
- **Names are stable and IPs are not.** Recreating `api` changed its ClusterIP,
  and the name kept working.
- **`ndots:5` makes short names convenient but costs extra queries** for
  external names. See [`../coredns/README.md`](../coredns/README.md), which
  captures the search-list walk for `example.com`.

Cleanup: `kubectl delete namespace s11-dns-a s11-dns-b`.
