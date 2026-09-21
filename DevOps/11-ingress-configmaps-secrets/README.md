# Ingress, ConfigMaps & Secrets — Homework

Session 12. Separating configuration from images, handling secrets, and putting
a single HTTP entry point in front of many Services.

Command results are **real captured output** from the three-node kind cluster
built in [assignment 08](../08-kubernetes-fundamentals/README.md), with the
ingress-nginx controller installed and kind mapping host ports **8080 → 80** and
**8443 → 443**.

---

## Task 1 — ConfigMap

[`manifests/01-configmap.yaml`](manifests/01-configmap.yaml) holds both shapes of
data a ConfigMap can carry: **five plain key–value pairs**, and **one whole file**.

```yaml
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  APP_PORT: "5000"
  DEFAULT_CURRENCY: "INR"
  MAX_BOOKING_DAYS: "30"

  app.properties: |
    server.name=yatri-booking
    server.timeout=30
    feature.new-checkout=enabled
```

```bash
$ kubectl apply -f manifests/01-configmap.yaml
configmap/app-config created

$ kubectl get configmap app-config
NAME         DATA   AGE
app-config   6      0s
```

`DATA 6` — five scalars plus the file all count as keys.

```bash
$ kubectl describe configmap app-config
Name:         app-config
Namespace:    default
Labels:       app=demo
Annotations:  <none>

Data
====
APP_PORT:
----
5000

DEFAULT_CURRENCY:
----
INR

ENVIRONMENT:
----
production

LOG_LEVEL:
----
INFO

MAX_BOOKING_DAYS:
----
30

app.properties:
----
server.name=yatri-booking
server.timeout=30
feature.new-checkout=enabled



BinaryData
====

Events:  <none>
```

**`describe` prints ConfigMap values in full.** Remember that when comparing with
the Secret below — it is the whole difference in how the two are treated.

```bash
$ kubectl get configmap app-config -o jsonpath='{.data.ENVIRONMENT}'; echo
production
```

---

## Task 2 — Secret, and the base64 trap

### The mistake that costs an afternoon

Before touching Secrets, the single most common error — `echo` adds a trailing
newline, and base64 faithfully encodes it:

```bash
$ echo 'S3cr3t-P@ss' | base64
UzNjcjN0LVBAc3MK

$ echo -n 'S3cr3t-P@ss' | base64
UzNjcjN0LVBAc3M=
```

Two different strings. Decoding both and looking at the raw bytes shows exactly
what went wrong:

```bash
$ echo 'UzNjcjN0LVBAc3MK' | base64 -d | xxd | tail -1
00000000: 5333 6372 3374 2d50 4073 730a            S3cr3t-P@ss.

$ echo 'UzNjcjN0LVBAc3M=' | base64 -d | xxd | tail -1
00000000: 5333 6372 3374 2d50 4073 73              S3cr3t-P@ss
```

That trailing **`0a`** is a newline character silently appended to the password.
The database rejects the login, the Secret *looks* completely correct in every
`kubectl` output, and nothing anywhere reports an error. **Always `echo -n`**, or
avoid the problem entirely with `kubectl create secret generic --from-literal`,
which never involves a shell pipeline.

### Creating and reading it

```bash
$ kubectl apply -f manifests/02-secret.yaml
secret/db-secret created

$ kubectl get secret db-secret
NAME        TYPE     DATA   AGE
db-secret   Opaque   2      0s

$ kubectl describe secret db-secret
Name:         db-secret
Namespace:    default
Labels:       <none>
Annotations:  <none>

Type:  Opaque

Data
====
DB_PASSWORD:  11 bytes
DB_USER:      5 bytes
```

Compare with the ConfigMap: `describe` shows **`11 bytes`**, not the value. That
is the only protection `describe` gives you, and it is cosmetic:

```bash
$ kubectl get secret db-secret -o jsonpath='{.data.DB_PASSWORD}'; echo
UzNjcjN0LVBAc3M=

$ kubectl get secret db-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d; echo
S3cr3t-P@ss
```

**Secrets are base64-encoded, not encrypted.** Anyone with `get secret`
permission has the plaintext, and by default etcd stores them unencrypted too.
Making them genuinely secret needs at least one of: RBAC that actually restricts
`get secret`, encryption-at-rest on etcd (`EncryptionConfiguration`), or an
external store (Vault, AWS/GCP secret managers, External Secrets Operator).

Base64 exists so that **binary** values (certificates, keystores) can live in
JSON. It was never a security feature.

---

## Task 3 — Consuming config: environment variables vs volumes

[`manifests/03-app.yaml`](manifests/03-app.yaml) consumes both objects both ways
at once.

### As environment variables

```yaml
env:
  - name: ENVIRONMENT
    valueFrom:
      configMapKeyRef: { name: app-config, key: ENVIRONMENT }
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef: { name: db-secret, key: DB_PASSWORD }
```

```bash
$ kubectl exec deploy/config-demo -- env | grep -E 'ENVIRONMENT|LOG_LEVEL|DB_USER|DB_PASSWORD' | sort
DB_PASSWORD=S3cr3t-P@ss
DB_USER=admin
ENVIRONMENT=production
LOG_LEVEL=INFO
```

Note `DB_PASSWORD=S3cr3t-P@ss` — **already decoded**. The kubelet does the base64
decoding; the application only ever sees plaintext. (Also note it has no trailing
newline, because the Secret was built with `echo -n`.)

### As mounted volumes

```bash
$ kubectl exec deploy/config-demo -- ls -l /etc/app-config
total 0
lrwxrwxrwx    1 root     root            15 Sep 21 09:17 APP_PORT -> ..data/APP_PORT
lrwxrwxrwx    1 root     root            23 Sep 21 09:17 DEFAULT_CURRENCY -> ..data/DEFAULT_CURRENCY
lrwxrwxrwx    1 root     root            18 Sep 21 09:17 ENVIRONMENT -> ..data/ENVIRONMENT
lrwxrwxrwx    1 root     root            16 Sep 21 09:17 LOG_LEVEL -> ..data/LOG_LEVEL
lrwxrwxrwx    1 root     root            23 Sep 21 09:17 MAX_BOOKING_DAYS -> ..data/MAX_BOOKING_DAYS
lrwxrwxrwx    1 root     root            21 Sep 21 09:17 app.properties -> ..data/app.properties
```

**Every key became a file, and every file is a symlink.** The reason is visible
one level down:

```bash
$ kubectl exec deploy/config-demo -- ls -la /etc/app-config
total 12
drwxrwxrwx    3 root     root          4096 Sep 21 09:17 .
drwxr-xr-x    1 root     root          4096 Sep 21 09:17 ..
drwxr-xr-x    2 root     root          4096 Sep 21 09:17 ..2026_09_21_09_17_55.1090508565
lrwxrwxrwx    1 root     root            32 Sep 21 09:17 ..data -> ..2026_09_21_09_17_55.1090508565
lrwxrwxrwx    1 root     root            15 Sep 21 09:17 APP_PORT -> ..data/APP_PORT
...
```

A timestamped directory holds the real data, `..data` is a symlink to it, and
every key is a symlink through `..data`. To update, the kubelet writes a *new*
timestamped directory and atomically swings the single `..data` symlink. An
application can never observe a half-updated config — either it sees all the old
values or all the new ones.

```bash
$ kubectl exec deploy/config-demo -- cat /etc/app-config/app.properties
server.name=yatri-booking
server.timeout=30
feature.new-checkout=enabled
```

A multi-line value mounts as a genuine config file, which is how you inject an
`nginx.conf` or `application.yaml` without rebuilding the image.

### Secret volumes live in RAM

```bash
$ kubectl exec deploy/config-demo -- df -h /etc/app-secret
Filesystem                Size      Used Available Use% Mounted on
tmpfs                    15.6G      8.0K     15.6G   0% /etc/app-secret
```

**`tmpfs`** — a Secret volume is never written to the node's disk. Kill the node
and the plaintext is gone with the RAM. ConfigMap volumes get no such treatment.

---

## Task 4 — What happens when config changes while pods are running

This is the most practically important behaviour in this session, and the two
consumption methods behave completely differently.

```bash
$ kubectl exec deploy/config-demo -- env | grep LOG_LEVEL
LOG_LEVEL=INFO

$ kubectl exec deploy/config-demo -- cat /etc/app-config/LOG_LEVEL; echo
INFO
```

Change the ConfigMap — **no pod restart, no redeploy**:

```bash
$ kubectl patch configmap app-config -p '{"data":{"LOG_LEVEL":"DEBUG"}}'
configmap/app-config patched

$ kubectl get configmap app-config -o jsonpath='{.data.LOG_LEVEL}'; echo
DEBUG
```

Polling the mounted file every 5 seconds:

```
  t+0s   volume=INFO
  t+5s   volume=INFO
  t+10s  volume=INFO
  t+15s  volume=INFO
  t+20s  volume=INFO
  t+25s  volume=INFO
  t+30s  volume=INFO
  t+35s  volume=INFO
  t+41s  volume=INFO
  t+46s  volume=INFO
  t+51s  volume=INFO
  t+56s  volume=DEBUG
```

**The mounted file updated by itself after 56 seconds.** No restart. The delay is
the kubelet's sync period (~60s by default) plus its cache TTL — updates are
eventually-consistent, not instant, which matters if you expect a config flag to
take effect immediately.

Meanwhile, in the very same container:

```bash
$ kubectl exec deploy/config-demo -- cat /etc/app-config/LOG_LEVEL; echo
DEBUG

$ kubectl exec deploy/config-demo -- env | grep LOG_LEVEL
LOG_LEVEL=INFO
```

**The volume says `DEBUG`; the environment variable still says `INFO`.**
Environment variables are injected once, at container start, into the process's
memory. Nothing can change them afterwards — that is a Linux fact, not a
Kubernetes limitation.

```bash
$ kubectl rollout restart deploy/config-demo
deployment.apps/config-demo restarted

$ kubectl exec deploy/config-demo -- env | grep LOG_LEVEL
LOG_LEVEL=DEBUG
```

| | Env var | Mounted volume |
|---|---|---|
| Updates without a restart | **No, ever** | **Yes**, after ~60s |
| Application must re-read the file | n/a | Yes — the file changes, the app may not notice |
| Good for | values fixed for a container's life | certificates, feature flags, hot-reloadable config |

The practical trap: a team mounts a ConfigMap as env vars, edits it, sees
`kubectl get configmap` show the new value, and cannot work out why the app still
behaves the old way. The answer is always `kubectl rollout restart`.

---

## Task 5 — Ingress: path-based routing

Three tiny apps stand behind it ([`manifests/04-backends.yaml`](manifests/04-backends.yaml)),
each serving its own name:

```bash
$ kubectl get deploy,svc -l app -o wide | head -20
NAME                          READY   UP-TO-DATE   AVAILABLE   AGE    CONTAINERS   IMAGES              SELECTOR
deployment.apps/admin         1/1     1            1           1s     web          nginx:1.27-alpine   app=admin
deployment.apps/backend       2/2     2            2           1s     web          nginx:1.27-alpine   app=backend
deployment.apps/config-demo   1/1     1            1           106s   app          busybox:1.36        app=config-demo
deployment.apps/frontend      2/2     2            2           1s     web          nginx:1.27-alpine   app=frontend
```

```bash
$ kubectl apply -f manifests/05-ingress-path.yaml
ingress.networking.k8s.io/path-ingress created

$ kubectl get ingress path-ingress
NAME           CLASS   HOSTS        ADDRESS     PORTS   AGE
path-ingress   nginx   shop.local   localhost   80      15s
```

```bash
$ kubectl describe ingress path-ingress | sed -n '/^Rules:/,/^Annotations:/p'
Rules:
  Host        Path  Backends
  ----        ----  --------
  shop.local
              /api(/|$)(.*)     backend-svc:80 (10.244.2.57:80,10.244.1.74:80)
              /admin(/|$)(.*)   admin-svc:80 (10.244.2.58:80)
              /()(.*)           frontend-svc:80 (10.244.1.73:80,10.244.2.56:80)
Annotations:  nginx.ingress.kubernetes.io/rewrite-target: /$2
```

`describe ingress` resolves each backend down to **actual pod IPs** — the fastest
way to confirm an Ingress rule is wired to something real rather than an empty
Service.

### Testing it

```bash
$ curl -s -H 'Host: shop.local' http://localhost:8080/
<h1>FRONTEND</h1>

$ curl -s -H 'Host: shop.local' http://localhost:8080/api
<h1>BACKEND API</h1>

$ curl -s -H 'Host: shop.local' http://localhost:8080/admin
<h1>ADMIN PANEL</h1>
```

**One IP, one port, three different applications** — chosen by URL path. That is
the entire value proposition against giving each service its own LoadBalancer
(and its own cloud bill, as measured in
[assignment 10](../10-kubernetes-services/README.md)).

### The rewrite annotation, and reading a 404 correctly

```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /$2
```

The path `/api(/|$)(.*)` has two capture groups; `$2` is everything after
`/api`. So a request for `/api/users` reaches the backend as `/users`. Without
this, the backend would receive `/api/users` and would need to know it is mounted
under `/api` — leaking routing topology into the application.

```bash
$ curl -s -H 'Host: shop.local' http://localhost:8080/anything/else
<html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx/1.27.5</center>
</body>
</html>
```

This 404 is a **success**, not a failure, and the signature proves it: the page
is served by **`nginx/1.27.5`** — the version in the `frontend` pod, not the
ingress controller. So routing worked, the request reached the frontend, and the
rewritten path `/else` simply does not exist there. An ingress-level "no rule
matched" 404 would instead be branded by the controller's own nginx build.

---

## Task 6 — Host-based routing

```bash
$ kubectl apply -f manifests/06-ingress-host.yaml
ingress.networking.k8s.io/host-ingress created

$ kubectl get ingress
NAME           CLASS   HOSTS                           ADDRESS     PORTS   AGE
host-ingress   nginx   www.shop.local,api.shop.local               80      12s
path-ingress   nginx   shop.local                      localhost   80      45s
```

```bash
$ curl -s -H 'Host: www.shop.local' http://localhost:8080/
<h1>FRONTEND</h1>

$ curl -s -H 'Host: api.shop.local' http://localhost:8080/
<h1>BACKEND API</h1>

$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' -H 'Host: unknown.shop.local' http://localhost:8080/
HTTP 404
```

**The same IP and the same port** returned different applications purely on the
`Host:` header, and an unmatched host got a clean 404. This is ordinary HTTP
virtual hosting — which is also why Ingress is **layer 7 and HTTP-only**. A
Postgres or Redis port cannot be routed this way; that still needs a Service of
type LoadBalancer or NodePort.

Note both Ingress objects coexist happily. The controller merges every Ingress in
the cluster into one nginx configuration.

---

## Task 7 — TLS termination

A self-signed certificate, stored in a Secret of the dedicated TLS type:

```bash
$ openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout tls.key -out tls.crt \
    -subj "/CN=secure.shop.local/O=devops-homework" \
    -addext "subjectAltName=DNS:secure.shop.local"

$ kubectl create secret tls shop-tls --cert=tls.crt --key=tls.key
secret/shop-tls created

$ kubectl get secret shop-tls
NAME       TYPE                DATA   AGE
shop-tls   kubernetes.io/tls   2      0s

$ kubectl describe secret shop-tls
Type:  kubernetes.io/tls

Data
====
tls.crt:  1245 bytes
tls.key:  1704 bytes
```

`kubernetes.io/tls` is a **typed** Secret, not `Opaque`: Kubernetes enforces that
it contains exactly the keys `tls.crt` and `tls.key`.

```yaml
spec:
  tls:
    - hosts: [secure.shop.local]
      secretName: shop-tls
```

```bash
$ kubectl get ingress tls-ingress
NAME          CLASS   HOSTS               ADDRESS   PORTS     AGE
tls-ingress   nginx   secure.shop.local             80, 443   15s
```

`PORTS` becomes `80, 443` as soon as a `tls:` block exists.

### A real trap: `-H 'Host:'` does not set SNI

The first attempt served the wrong certificate entirely:

```bash
$ curl -skv https://localhost:8443/ -H 'Host: secure.shop.local' 2>&1 | grep -E 'subject:|issuer:'
*  subject: O=Acme Co; CN=Kubernetes Ingress Controller Fake Certificate
*  issuer: O=Acme Co; CN=Kubernetes Ingress Controller Fake Certificate
```

That is ingress-nginx's built-in placeholder certificate, not `shop-tls`. The
reason is ordering: **TLS is negotiated before any HTTP is sent.** `-H 'Host:'`
sets an HTTP header, which the server cannot see until the handshake is already
finished. The name used to select a certificate is the TLS **SNI** field, which
curl takes from the URL — and the URL said `localhost`.

`--resolve` fixes it by letting curl connect *as* `secure.shop.local` while still
dialling `127.0.0.1`:

```bash
$ curl -skv --resolve secure.shop.local:8443:127.0.0.1 https://secure.shop.local:8443/ 2>&1 | grep -E 'subject:|issuer:|expire date:'
*  subject: CN=secure.shop.local; O=devops-homework
*  expire date: Sep 21 09:20:14 2027 GMT
*  issuer: CN=secure.shop.local; O=devops-homework

$ curl -sk --resolve secure.shop.local:8443:127.0.0.1 https://secure.shop.local:8443/
<h1>FRONTEND</h1>
```

Now the correct certificate is served. This is worth internalising, because the
identical mistake in production looks like "the ingress is serving the wrong
site's certificate" when the real cause is a client not sending SNI.

### Verifying properly, without `-k`

```bash
$ curl -s --resolve secure.shop.local:8443:127.0.0.1 --cacert tls.crt https://secure.shop.local:8443/
<h1>FRONTEND</h1>
```

Full certificate validation passes when the self-signed cert is supplied as the
trusted CA. And without it, validation correctly fails:

```bash
$ curl -s --resolve secure.shop.local:8443:127.0.0.1 https://secure.shop.local:8443/; echo "curl exit=$?"
curl exit=60
```

Exit **60** is *peer certificate cannot be authenticated with known CA
certificates* — the right answer for a self-signed certificate. A real deployment
replaces this step with cert-manager and Let's Encrypt.

Note also that TLS terminates **at the ingress controller**. Traffic from the
controller to `frontend-svc` is plain HTTP inside the cluster.

---

## Task 8 — How the pieces fit

```
                        ┌───────────────────────────────────────────┐
   curl / browser       │  ingress-nginx controller                 │
        │               │  (one Service, one external entry point)  │
        │  :8080 http   │                                           │
        └──────────────►│  Host: shop.local      /api    ──────┐    │
           :8443 https  │  Host: shop.local      /admin  ────┐ │    │
                        │  Host: www.shop.local  /      ──┐  │ │    │
                        │  Host: secure.shop.local  (TLS) │  │ │    │
                        └─────────────────────────────────┼──┼─┼────┘
                                                          │  │ │
                            ┌─────────────────────────────┘  │ │
                            │        ┌───────────────────────┘ │
                            │        │            ┌────────────┘
                     ┌──────▼─────┐ ┌▼──────────┐ ┌▼──────────┐
                     │frontend-svc│ │ admin-svc │ │backend-svc│
                     └──────┬─────┘ └─────┬─────┘ └─────┬─────┘
                            │             │             │
                        [2 pods]      [1 pod]       [2 pods]
                            │
                    ┌───────▼────────────────────────┐
                    │ env  ◄── ConfigMap app-config  │  (needs restart)
                    │ vol  ◄── ConfigMap app-config  │  (auto, ~60s)
                    │ env  ◄── Secret db-secret      │
                    │ vol  ◄── Secret db-secret      │  (tmpfs)
                    └────────────────────────────────┘
```

---

## What I took away

- **`echo` vs `echo -n` is a real, silent bug.** The `xxd` output made the stray
  `0a` byte visible; nothing in `kubectl` ever would.
- **Secrets are encoded, not encrypted.** `describe` hides the value, `get -o
  jsonpath` hands it straight over. Real protection is RBAC, etcd encryption, or
  an external store.
- **Env vars never update; volumes update after about a minute.** Measured at 56
  seconds. This single fact explains most "my config change did nothing" reports.
- **The `..data` symlink is why config updates are atomic** — one symlink swap,
  never a partially-written directory.
- **Secret volumes are `tmpfs`**, so plaintext never reaches the node's disk.
- **`-H 'Host:'` does not set TLS SNI.** The header arrives after the handshake
  that already chose a certificate; `--resolve` is the correct tool.
- **Ingress is HTTP-only, layer 7.** Databases still need NodePort or
  LoadBalancer.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Create a ConfigMap | Done — 6 keys, scalars **and** an embedded file |
| 1 | Inspect it (`get` / `describe` / jsonpath) | Done — values printed in full |
| 2 | Understand the base64 newline gotcha | Done — proven byte-for-byte with `xxd` |
| 2 | Create a Secret | Done — `db-secret`, Opaque, 2 keys |
| 2 | Show Secrets are encoded, not encrypted | Done — plaintext recovered with one command |
| 3 | Consume config as environment variables | Done — decoded automatically by the kubelet |
| 3 | Consume config as mounted volumes | Done — incl. the `..data` atomic-update symlink farm |
| 3 | Secret volume characteristics | Done — confirmed `tmpfs`, never on node disk |
| 4 | Behaviour on config change | Done — **volume updated at 56s, env var never did** |
| 4 | Force a pickup | Done — `kubectl rollout restart` |
| 5 | Create an Ingress with path routing | Done — `/`, `/api`, `/admin` → 3 services |
| 5 | Understand `rewrite-target` | Done — incl. reading the backend-branded 404 correctly |
| 6 | Host-based routing | Done — 2 hostnames, same IP/port, unmatched host → 404 |
| 7 | TLS termination | Done — `kubernetes.io/tls` Secret, correct cert served |
| 7 | Verify the certificate | Done — incl. the SNI trap and a clean `--cacert` validation |

## Raw evidence

The [evidence directory](evidence/) preserves the original command transcripts,
including failed attempts and intermediate states. YAML listings are configuration,
and explanatory tables or shortened excerpts summarize those captures.
