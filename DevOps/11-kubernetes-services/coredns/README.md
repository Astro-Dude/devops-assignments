# CoreDNS — the Cluster's DNS Server

Session 11, Task 4. What CoreDNS is, why Kubernetes uses it, how service
discovery and query resolution work, the real configuration running in the
cluster, and how to troubleshoot DNS.

All output is **real captured output** from the single-node kind cluster
`hw-legacy` (Kubernetes v1.37, CoreDNS 1.14.6), using the namespaces and client
Pod from the [FQDN lab](../fqdn/README.md). The broken/fixed Pods are
[`broken-dns-pod.yaml`](broken-dns-pod.yaml) and
[`fixed-dns-pod.yaml`](fixed-dns-pod.yaml). Full transcript:
[`../evidence/s11-coredns-lab.txt`](../evidence/s11-coredns-lab.txt). CoreDNS
was only **inspected** here. Its ConfigMap and Deployment were not changed,
because other labs share this cluster.

---

## 1. What is CoreDNS?

CoreDNS is a DNS server written in Go and built from **plugins**. Every feature
(serving Kubernetes records, caching, forwarding, metrics, health checks) is a
plugin, enabled with one line in a config file called the **Corefile**. It is a
CNCF graduated project, and it has been the default cluster DNS since
Kubernetes 1.13, replacing `kube-dns` (dnsmasq + skydns). The Service is still
called `kube-dns` for compatibility.

## 2. Why Kubernetes uses it

- **Pods and Services come and go constantly.** A DNS server has to watch the
  API and answer with the current state. CoreDNS's `kubernetes` plugin does
  that, with no zone files to edit.
- **One small process does it all:** cluster records, upstream forwarding,
  cache, metrics, health checks. kube-dns needed three containers.
- **Configurable without rebuilding:** stub domains, rewrites and custom hosts
  are a Corefile edit, picked up live by the `reload` plugin.

---

## 3. CoreDNS in this cluster

```console
$ kubectl -n kube-system get deploy coredns -o wide
NAME      READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                                    SELECTOR
coredns   2/2     2            2           25m   coredns      registry.k8s.io/coredns/coredns:v1.14.6   k8s-app=kube-dns

$ kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
NAME                       READY   STATUS    RESTARTS   AGE   IP           NODE
coredns-559f6c778d-5bxcs   1/1     Running   0          25m   10.244.0.4   hw-legacy-control-plane
coredns-559f6c778d-mps4k   1/1     Running   0          25m   10.244.0.3   hw-legacy-control-plane

$ kubectl -n kube-system get svc kube-dns
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   25m

$ kubectl -n kube-system get endpointslices -l kubernetes.io/service-name=kube-dns
NAME             ADDRESSTYPE   PORTS        ENDPOINTS               AGE
kube-dns-qt6dw   IPv4          53,53,9153   10.244.0.3,10.244.0.4   25m
```

CoreDNS is just a Deployment with **2 replicas** behind an ordinary ClusterIP
Service, **`10.96.0.10`**. That is the address the kubelet writes into every
Pod:

```console
$ kubectl -n s11-dns-a exec client -- cat /etc/resolv.conf
search s11-dns-a.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

It is allowed to **list and watch** exactly the objects it needs to answer
queries:

```console
$ kubectl get clusterrole system:coredns -o jsonpath='{range .rules[*]}{.resources} {.verbs}{"\n"}{end}'
["endpoints","services","pods","namespaces"] ["list","watch"]
["endpointslices"] ["list","watch"]
```

---

## 4. CoreDNS configuration: the Corefile

```console
$ kubectl -n kube-system get configmap coredns -o yaml
data:
  Corefile: |
    .:53 {
        errors
        health {
           lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
           ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf {
           max_concurrent 1000
        }
        cache 30 {
           disable success cluster.local
           disable denial cluster.local
        }
        loop
        reload
        loadbalance
    }
```

The Deployment mounts this ConfigMap and starts CoreDNS with `-conf
/etc/coredns/Corefile`.

| Line | What it does |
|---|---|
| `.:53` | one server block for **all** names (`.`), on port 53 |
| `errors` | log errors to stdout (that is all `kubectl logs` shows by default) |
| `health { lameduck 5s }` | `:8080/health` liveness endpoint; on shutdown keep answering for 5 s so in-flight queries finish |
| `ready` | `:8181/ready` readiness endpoint. The Pod only joins `kube-dns` once all plugins are ready |
| `kubernetes cluster.local in-addr.arpa ip6.arpa` | **the service-discovery plugin**: answers `cluster.local` names and reverse lookups from its API watch |
| `pods insecure` | enables `<ip-dashed>.<ns>.pod.cluster.local` records without checking the Pod exists |
| `fallthrough in-addr.arpa ip6.arpa` | reverse lookups for non-cluster IPs go on to the next plugin instead of NXDOMAIN |
| `ttl 30` | records are cacheable for 30 s (seen as `30` in every `dig` answer) |
| `prometheus :9153` | metrics on port 9153 (the third port on the Service) |
| `forward . /etc/resolv.conf` | anything not in the cluster zone goes to the **node's** upstream resolver |
| `cache 30 { disable success/denial cluster.local }` | cache external answers for 30 s, but **never cache cluster.local**, so Service changes show up straight away |
| `loop` | detects forwarding loops (CoreDNS forwarding to itself) and stops instead of spinning |
| `reload` | re-reads the Corefile when the ConfigMap changes; no restart needed |
| `loadbalance` | shuffles the order of A records in each answer (round-robin for headless Services) |

To customise it you edit this ConfigMap. Common changes are a stub domain
(`corp.example:53 { forward . 10.0.0.53 }`), `rewrite`, or `hosts`. `reload`
picks up the edit within about 30 s.

---

## 5. How service discovery works

1. CoreDNS's `kubernetes` plugin **watches** Services, EndpointSlices, Pods and
   Namespaces through the API server, and keeps them in memory.
2. A Service named `X` in namespace `N` immediately becomes
   `X.N.svc.cluster.local` → ClusterIP (or → Pod IPs if headless). No DNS
   record is ever "registered" by hand.

Proved live: the name does not exist, a Service is created, and the name
resolves straight away:

```console
$ kubectl -n s11-dns-a exec client -- dig +short brand-new.s11-dns-a.svc.cluster.local; echo "(empty = NXDOMAIN)"
(empty = NXDOMAIN)

$ kubectl -n s11-dns-a create service clusterip brand-new --tcp=80:80
service/brand-new created

$ kubectl -n s11-dns-a exec client -- dig +short brand-new.s11-dns-a.svc.cluster.local
10.96.44.197

$ kubectl -n s11-dns-a get svc brand-new
NAME        TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
brand-new   ClusterIP   10.96.44.197   <none>        80/TCP    0s
```

The Service was `0s` old and already in DNS. It was not cached as NXDOMAIN
from a moment earlier, because of `disable denial cluster.local`.

---

## 6. How DNS queries are resolved

```
app: getaddrinfo("example.com")
  │  resolv.conf: ndots:5, and "example.com" has 1 dot  -> try the search list first
  ├─> example.com.s11-dns-a.svc.cluster.local ─┐
  ├─> example.com.svc.cluster.local           ├─ CoreDNS kubernetes plugin: authoritative NXDOMAIN
  ├─> example.com.cluster.local               ─┘
  └─> example.com.  ── not cluster.local ──> forward plugin -> node's resolver -> internet
                                              (answer cached 30 s)
```

`dig` normally ignores the search list. With `+search +showsearch` it walks it
the way a normal application does, and prints every attempt:

```console
$ kubectl -n s11-dns-a exec client -- dig +search +showsearch +noall +answer +comments example.com
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 45778
;; flags: qr aa rd; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 23354
;; flags: qr aa rd; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 24738
;; flags: qr aa rd; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 63666
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1
;; ANSWER SECTION:
example.com.		15	IN	A	172.66.147.243
example.com.		15	IN	A	104.20.23.154
```

(dig's "WARNING: .local is reserved for Multicast DNS" lines are removed above;
they are in the transcript.) There are **four queries for one name**: three
NXDOMAINs answered by CoreDNS itself, with `aa` (authoritative) and no `ra`,
then the real answer, forwarded upstream, with `ra` (recursion available). The
same walk done by hand, one name at a time:

```console
$ kubectl -n s11-dns-a exec client -- dig +noall +comments +answer example.com.s11-dns-a.svc.cluster.local | grep -E 'status:|IN\s+A'
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 21640
$ kubectl -n s11-dns-a exec client -- dig +noall +comments +answer example.com.svc.cluster.local | grep -E 'status:|IN\s+A'
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 12516
$ kubectl -n s11-dns-a exec client -- dig +noall +comments +answer example.com.cluster.local | grep -E 'status:|IN\s+A'
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 9665
$ kubectl -n s11-dns-a exec client -- dig +noall +comments +answer example.com. | grep -E 'status:|IN\s+A'
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 52555
example.com.		15	IN	A	172.66.147.243
example.com.		15	IN	A	104.20.23.154
```

A cluster name, by contrast, is found on the **first** try:

```console
$ kubectl -n s11-dns-a exec client -- dig +search +showsearch +noall +answer +comments api
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 55397
;; flags: qr aa rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
;; ANSWER SECTION:
api.s11-dns-a.svc.cluster.local. 30 IN	A	10.96.98.48
```

So `ndots:5` makes in-cluster short names cheap and external names expensive.
The fix for hot external names is a trailing dot (`example.com.`) or a lower
`ndots` in the Pod's `dnsConfig`.

---

## 7. Troubleshooting DNS

### Checklist (cheapest first)

```bash
# 1. Is CoreDNS running and does the Service have endpoints?
kubectl -n kube-system get pods -l k8s-app=kube-dns
kubectl -n kube-system get endpointslices -l kubernetes.io/service-name=kube-dns
# 2. Does DNS work from a known-good Pod? (isolates "cluster DNS" from "this Pod")
kubectl exec <good-pod> -- nslookup kubernetes.default
# 3. What resolver does the failing Pod actually use?
kubectl exec <pod> -- cat /etc/resolv.conf
kubectl get pod <pod> -o jsonpath='{.spec.dnsPolicy} {.spec.dnsConfig}'
# 4. Query CoreDNS directly, bypassing the Pod's config
kubectl exec <pod> -- nslookup <name> 10.96.0.10
# 5. Does the name exist? Right namespace?
kubectl get svc -A --field-selector metadata.name=<svc>
# 6. CoreDNS's own view
kubectl -n kube-system logs -l k8s-app=kube-dns
kubectl -n kube-system get configmap coredns -o yaml
```

How to read the error:

| Symptom | Meaning |
|---|---|
| `connection timed out; no servers could be reached` | the resolver cannot reach a DNS server at all (wrong nameserver, CoreDNS down, network policy blocking UDP 53) |
| `NXDOMAIN` / curl exit code 6 | DNS works, but **that name does not exist** (typo, wrong namespace, Service not created) |
| resolves, but connection fails | not DNS. Check the Service's endpoints and ports |

### Scenario 1 — a Pod that cannot resolve anything

[`broken-dns-pod.yaml`](broken-dns-pod.yaml) sets `dnsPolicy: None` and a
nameserver, `10.96.0.99`, that nothing listens on. That is a realistic
copy-paste mistake from an old manifest.

**Identify:**

```console
$ kubectl -n s11-dns-a exec dns-broken -- nslookup -timeout=2 api
;; connection timed out; no servers could be reached
command terminated with exit code 1

$ kubectl -n s11-dns-a exec dns-broken -- wget -q -O- -T 3 http://api
wget: bad address 'api'
```

**Investigate.** Step 1: is CoreDNS healthy? Yes, and another Pod resolves the
same name:

```console
$ kubectl -n kube-system get pods -l k8s-app=kube-dns
NAME                       READY   STATUS    RESTARTS   AGE
coredns-559f6c778d-5bxcs   1/1     Running   0          26m
coredns-559f6c778d-mps4k   1/1     Running   0          26m

$ kubectl -n s11-dns-a exec client -- nslookup api
Name:	api.s11-dns-a.svc.cluster.local
Address: 10.96.98.48
```

Step 2: what resolver is *this* Pod using?

```console
$ kubectl -n s11-dns-a exec dns-broken -- cat /etc/resolv.conf
search s11-dns-a.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.99
options ndots:5

$ kubectl -n s11-dns-a get pod dns-broken -o jsonpath='dnsPolicy={.spec.dnsPolicy} dnsConfig={.spec.dnsConfig}'
dnsPolicy=None dnsConfig={"nameservers":["10.96.0.99"],"options":[{"name":"ndots","value":"5"}],"searches":["s11-dns-a.svc.cluster.local","svc.cluster.local","cluster.local"]}
```

Step 3: does the Pod work when pointed at the real DNS Service?

```console
$ kubectl -n s11-dns-a exec dns-broken -- nslookup api.s11-dns-a.svc.cluster.local 10.96.0.10
Server:		10.96.0.10
Address:	10.96.0.10:53

Name:	api.s11-dns-a.svc.cluster.local
Address: 10.96.98.48
```

**Root cause:** `dnsPolicy: None` + `nameserver 10.96.0.99`. The Pod's network
is fine and CoreDNS is fine; the Pod was told to ask the wrong server.

**Fix:** `dnsConfig` is immutable on a running Pod, so recreate it with the
default `dnsPolicy: ClusterFirst` ([`fixed-dns-pod.yaml`](fixed-dns-pod.yaml)).

**Verify:**

```console
$ kubectl -n s11-dns-a exec dns-broken -- cat /etc/resolv.conf
search s11-dns-a.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5

$ kubectl -n s11-dns-a exec dns-broken -- wget -q -O- -T 3 http://api
api answering from namespace s11-dns-a
```

(Busybox's `nslookup` on the fixed Pod also printed `can't find
api.cluster.local: NXDOMAIN` lines next to the correct answer. It sends every
search-list variant, A and AAAA, and prints all the failures. The `wget` above
shows that resolution works.)

### Scenario 2 — NXDOMAIN because the Service lives in another namespace

```console
$ kubectl -n s11-dns-a exec client -- curl -s --max-time 3 http://payments
command terminated with exit code 6

$ kubectl -n s11-dns-a exec client -- nslookup payments
** server can't find payments: NXDOMAIN
```

DNS answered, so the server is fine and the name is wrong. Where does
`payments` actually live?

```console
$ kubectl get svc -A --field-selector metadata.name=payments
NAMESPACE   NAME       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
s11-dns-b   payments   ClusterIP   10.96.137.166   <none>        80/TCP    2s
```

**Root cause:** the client is in `s11-dns-a`. The short name expands to
`payments.s11-dns-a.svc.cluster.local`, which does not exist. **Fix:** use
`<svc>.<ns>` or the full FQDN:

```console
$ kubectl -n s11-dns-a exec client -- curl -s -o /dev/null -w '%{http_code}\n' http://payments.s11-dns-b
200
$ kubectl -n s11-dns-a exec client -- curl -s -o /dev/null -w '%{http_code}\n' http://payments.s11-dns-b.svc.cluster.local
200
```

### CoreDNS's own logs and metrics

```console
$ kubectl -n kube-system logs -l k8s-app=kube-dns --tail=10
.:53
[INFO] plugin/reload: Running configuration SHA512 = 1b226df79860026c6a52e67daa10d7f0d57ec5b023288ec00c5e05f93523c894564e15b91770d3a07ae1cfbe861d15b37d4a0027e69c546ab112970993a3b03b
CoreDNS-1.14.6
linux/arm64, go1.26.5, 424d125
(same for the second replica)
```

The logs are quiet on purpose. The Corefile has `errors` but not `log`, so
individual queries (including all the NXDOMAINs above) are **not** logged. To
see every query you would add `log` to the Corefile temporarily. I did not do
that here because the cluster is shared. The `prometheus` plugin still counts
everything:

```console
$ kubectl -n kube-system get --raw /api/v1/namespaces/kube-system/pods/<coredns-pod>:9153/proxy/metrics | grep '^coredns_dns_responses_total'
coredns_dns_responses_total{plugin="errors",rcode="NOERROR",server="dns://:53",view="",zone="."} 169673
coredns_dns_responses_total{plugin="errors",rcode="NXDOMAIN",server="dns://:53",view="",zone="."} 38
```

That counter is one CoreDNS Pod's lifetime total for this shared cluster. A
rising NXDOMAIN rate is the first metric to check when apps report "random"
lookup failures.

## Takeaways

- CoreDNS is an ordinary Deployment + Service (`10.96.0.10`). Every Pod's
  `/etc/resolv.conf` points at it unless `dnsPolicy` says otherwise.
- Service discovery is a **watch**, not registration. A new Service resolved
  at age `0s`.
- `ndots:5` + the search list mean one external lookup cost **four queries**
  here.
- **Timeout = cannot reach a DNS server. NXDOMAIN = reached it, the name is
  wrong.** Telling those two apart is most of DNS troubleshooting.

Cleanup: `kubectl delete namespace s11-dns-a s11-dns-b`.
