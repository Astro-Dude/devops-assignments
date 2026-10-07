# Final Troubleshooting Challenge

I wrote [`broken-stack.yaml`](broken-stack.yaml), a copy of the TicketHub deployment with **seven deliberately planted faults**, and deployed it to its own namespace (`tickethub-broken`, host `broken.tickethub.localtest.me`) on the `hw-s21` kind cluster. Then I worked through it the way you would on call, one symptom at a time. For each fault the steps are: **identify → investigate logs/resources → root cause → fix → verify**. Every fix was first applied live with `kubectl`, then written back into [`fixed-stack.yaml`](fixed-stack.yaml). Each fix there is marked `# FIX n`.

All output below is real and was copied from the transcripts in [`../evidence/troubleshooting-*.txt`](../evidence/).

| # | Planted fault | First symptom | Where the clue was |
|---|---|---|---|
| 1 | Secret key name wrong (`password` instead of `DB_PASSWORD`) | postgres `CreateContainerConfigError` | `describe pod` events |
| 2 | Image tag `:latest` that CI never publishes | backend `Init:ImagePullBackOff` | `describe pod` + registry tag list |
| 3 | ConfigMap missing the `DB_HOST` key | initContainer loops "waiting for database" | initContainer logs + effective config |
| 4 | Readiness probe path `/readyz` (app serves `/ready`) | `Running` but `0/1` Ready | probe events + app access log |
| 5 | frontend Service `targetPort: 80` (nginx listens on 8080) | `502` on `/` with all pods Ready | ingress-nginx error log, endpoints |
| 6 | Ingress `/api` backend port `8080` (Service exposes 8000) | `503` on `/api/*` | `describe ingress` |
| 7 | HPA on a Deployment with no resource requests | HPA `cpu: <unknown>` forever | HPA conditions |

## 0. Deploy the broken stack and look at it from the outside

```
$ kubectl create namespace tickethub-broken
$ kubectl -n tickethub-broken create secret generic tickethub-db --from-literal=DB_USER=tickethub --from-literal=DB_PASSWORD="$(openssl rand -hex 16)"
$ kubectl apply -f troubleshooting/broken-stack.yaml

# ---- 45 seconds later: what does the user see?
GET /          -> 502
GET /api/stats -> 503

$ kubectl -n tickethub-broken get pods,svc,endpoints,ingress,hpa,pvc
NAME                                      READY   STATUS                       RESTARTS   AGE
pod/tickethub-backend-55fdc857f7-65lsg    0/1     Init:ImagePullBackOff        0          45s
pod/tickethub-frontend-6fffd56df7-jnzxq   1/1     Running                      0          45s
pod/tickethub-postgres-76f88d9556-4vhhl   0/1     CreateContainerConfigError   0          45s

NAME                           ENDPOINTS        AGE
endpoints/tickethub-backend                     45s
endpoints/tickethub-frontend   10.244.0.56:80   45s
endpoints/tickethub-postgres                    45s

NAME                                                    REFERENCE                      TARGETS              MINPODS   MAXPODS   REPLICAS
horizontalpodautoscaler.autoscaling/tickethub-backend   Deployment/tickethub-backend   cpu: <unknown>/70%   1         3         1
```

Two pods are failing and the only "healthy" one (frontend) still returns 502. I started at the bottom of the dependency chain, the database, because nothing above it can work until it does.

---

## Issue 1: postgres `CreateContainerConfigError` (wrong Secret key)

**Identify.** `tickethub-postgres-…   0/1   CreateContainerConfigError`. The container was never even created, so `kubectl logs` has nothing to show. The kubelet's reason is in the pod events.

**Investigate.**
```
$ kubectl -n tickethub-broken describe pod -l app.kubernetes.io/name=tickethub-postgres | sed -n '/^Events:/,$p'
  Warning  Failed     9s (x5 over 49s)  kubelet  spec.containers{postgres}: Error: couldn't find key password in Secret tickethub-broken/tickethub-db

$ kubectl -n tickethub-broken get secret tickethub-db -o jsonpath='{.data}' | jq 'keys'
[
  "DB_PASSWORD",
  "DB_USER"
]

$ kubectl -n tickethub-broken get deploy tickethub-postgres -o jsonpath='{.spec.template.spec.containers[0].env[2]}' | jq .
{ "name": "POSTGRES_PASSWORD", "valueFrom": { "secretKeyRef": { "key": "password", "name": "tickethub-db" } } }
```

**Root cause.** `secretKeyRef.key: password` points to a key the Secret doesn't have. The Secret exists and the pod is allowed to read it. Only the key name is wrong. I listed the key names with `jq 'keys'`, so the values were never printed.

**Fix.**
```
$ kubectl -n tickethub-broken patch deploy tickethub-postgres --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/key","value":"DB_PASSWORD"}]'
deployment.apps/tickethub-postgres patched
```

**Verify.** My first `pg_isready` ran one second after the new pod started and got `no response`, which is a real timing artefact. After the pod passed its readiness probe:
```
$ kubectl -n tickethub-broken get endpoints tickethub-postgres
NAME                 ENDPOINTS          AGE
tickethub-postgres   10.244.0.59:5432   60s
$ kubectl -n tickethub-broken exec deploy/tickethub-postgres -- sh -c "pg_isready -U \$POSTGRES_USER -d \$POSTGRES_DB"
/var/run/postgresql:5432 - accepting connections
```

## Issue 2: backend `Init:ImagePullBackOff` (non-existent tag)

**Identify / investigate.**
```
$ kubectl -n tickethub-broken describe pod -l app.kubernetes.io/name=tickethub-backend | grep -E 'Image:|Failed|BackOff'
    Image:          ghcr.io/astro-dude/s21-tickethub-backend:latest
  Warning  Failed     28s (x3 over 68s)  kubelet  spec.initContainers{migrate}: Failed to pull image "ghcr.io/astro-dude/s21-tickethub-backend:latest": rpc error: code = NotFound ...
  Normal   BackOff    4s (x4 over 68s)   kubelet  spec.initContainers{migrate}: Back-off pulling image "ghcr.io/astro-dude/s21-tickethub-backend:latest"

# which tags actually exist in the registry? (anonymous token, the package is public)
$ T=$(curl -s "https://ghcr.io/token?scope=repository:astro-dude/s21-tickethub-backend:pull" | jq -r .token); curl -s -H "Authorization: Bearer $T" https://ghcr.io/v2/astro-dude/s21-tickethub-backend/tags/list | jq -c .
{"name":"astro-dude/s21-tickethub-backend","tags":["055734260abf…","c9ba4c7618f8…","ac6fcbbdca7f…","25d422506213…","0b9665e38a2d…"]}
```

**Root cause.** The error is `NotFound`, not `unauthorized`, so this is not a pull-secret or visibility problem. The tag simply doesn't exist. The CI pipeline publishes **only immutable git-SHA tags**, on purpose: `:latest` can't tell you which commit is running, and two nodes can end up running two different "latest" images.

**Fix.** Pin both the initContainer and the main container to a SHA that CI built, scanned and pushed:
```
$ kubectl -n tickethub-broken set image deploy/tickethub-backend migrate=ghcr.io/astro-dude/s21-tickethub-backend:0b9665e38a2db926e487fe72e9283d84e672c0d5 backend=ghcr.io/astro-dude/s21-tickethub-backend:0b9665e38a2db926e487fe72e9283d84e672c0d5
deployment.apps/tickethub-backend image updated
```

**Verify.** The image now pulls, and the digest is recorded. The pod then moves on to the next problem:
```
NAME                                 READY   STATUS                  RESTARTS   AGE
tickethub-backend-55fdc857f7-65lsg   0/1     Init:ImagePullBackOff   0          95s   <- old ReplicaSet, being replaced
tickethub-backend-db745d98f-9lvkr    0/1     Init:0/1                0          25s
migrate: image=ghcr.io/astro-dude/s21-tickethub-backend:0b9665e… imageID=ghcr.io/astro-dude/s21-tickethub-backend@sha256:ad9ab2db419c…
```

## Issue 3: initContainer stuck "waiting for database" (missing ConfigMap key)

**Identify / investigate.** `Init:0/1` that never finishes, so I read the initContainer's log and then checked which settings the app actually loaded:
```
$ kubectl -n tickethub-broken logs pod/tickethub-backend-db745d98f-9lvkr -c migrate --tail=6
waiting for database ...
waiting for database ...

$ kubectl -n tickethub-broken exec pod/tickethub-backend-db745d98f-9lvkr -c migrate -- python -c 'from app.config import settings; print(settings.db_host, settings.db_port, settings.db_name)'
localhost 5432 tickethub

$ kubectl -n tickethub-broken get configmap tickethub-config -o jsonpath='{.data}' | jq .
{ "APP_ENV": "troubleshooting", "DB_NAME": "tickethub", "DB_PORT": "5432", "LOG_LEVEL": "INFO" }
```

**Root cause.** The ConfigMap has no `DB_HOST` key, so the app falls back to its default, `localhost`. Nothing listens on 5432 inside the backend pod. An `envFrom` with a missing key fails silently, unlike issue 1's `secretKeyRef`, which fails loudly. That is why this fault is harder to spot.

**Fix.** Add the key, then restart. `envFrom` is read only when a container starts, so patching the ConfigMap by itself changes nothing.
```
$ kubectl -n tickethub-broken patch configmap tickethub-config --type=merge -p '{"data":{"DB_HOST":"tickethub-postgres","DEFAULT_TEAM":"L1 Support"}}'
$ kubectl -n tickethub-broken rollout restart deploy/tickethub-backend
```
The Helm chart avoids this whole class of bug by putting a `checksum/config` annotation on the pod template, so any ConfigMap change rolls the pods.

**Verify.**
```
$ kubectl -n tickethub-broken logs pod/tickethub-backend-6c45b6756f-jn7mh -c migrate
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_create_tickets, create tickets table
INFO  [alembic.runtime.migration] Running upgrade 0001_create_tickets -> 0002_create_comments, create comments table
migrations applied (alembic head)
```

## Issue 4: backend `Running` but never Ready (wrong probe path)

**Identify / investigate.**
```
$ kubectl -n tickethub-broken get pods -l app.kubernetes.io/name=tickethub-backend
tickethub-backend-6c45b6756f-jn7mh   0/1     Running      0          39s

$ kubectl -n tickethub-broken describe pod/tickethub-backend-6c45b6756f-jn7mh | grep -E 'Readiness|Unhealthy'
    Readiness:      http-get http://:http/readyz delay=0s timeout=1s period=5s #success=1 #failure=3
  Warning  Unhealthy  4s (x6 over 29s)   kubelet  Readiness probe failed: HTTP probe failed with statuscode: 404

$ kubectl -n tickethub-broken logs pod/tickethub-backend-6c45b6756f-jn7mh -c backend --tail=3
{"ts": "2026-10-07T14:39:58", "level": "INFO", "logger": "tickethub", "msg": "request", ... "method": "GET", "path": "/readyz", "status": 404, "duration_ms": 0.33}
```

**Root cause.** The probe calls `/readyz`. The API serves `/ready`, which checks the database, and `/health`, which only checks the process. A 404 counts as a probe failure, so the pod never joins the Service. The app's own structured access log shows the bad path right away.

One more thing I learned here: `kubectl get endpointslice` printed both pod IPs in its `ENDPOINTS` column even while one pod was not Ready. EndpointSlices list *not-ready* addresses too, and the ready flag is in `.conditions.ready`. The old `get endpoints` view only shows ready addresses.

**Fix / verify.**
```
$ kubectl -n tickethub-broken patch deploy tickethub-backend --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/ready"}]'
$ kubectl -n tickethub-broken get endpointslice -l kubernetes.io/service-name=tickethub-backend -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]} ready={.conditions.ready} pod={.targetRef.name}{"\n"}{end}'
10.244.0.62 ready=true pod=tickethub-backend-67d6db5695-4hztw
$ kubectl -n tickethub-broken exec deploy/tickethub-backend -c backend -- python -c "...urlopen('http://127.0.0.1:8000/ready')..."
/ready -> {"status":"READY"}
```

## Issue 5: `502` on `/` although every pod is Ready (Service targetPort)

**Identify / investigate.**
```
$ curl -s -o /dev/null -w "GET / -> %{http_code}\n" http://broken.tickethub.localtest.me:28080/
GET / -> 502

$ kubectl -n tickethub-broken get endpoints tickethub-frontend
tickethub-frontend   10.244.0.56:80   3m11s
$ kubectl -n tickethub-broken get pod -l app.kubernetes.io/name=tickethub-frontend -o jsonpath='{.items[0].spec.containers[0].ports}'
[{"containerPort":8080,"protocol":"TCP"}]
$ kubectl -n tickethub-broken exec deploy/tickethub-frontend -- sh -c 'wget -qO- -T 2 http://127.0.0.1:80/ ... ; wget -qO- -T 2 http://127.0.0.1:8080/nginx-health'
wget: can't connect to remote host (127.0.0.1): Connection refused
port80 refused
ok
```

**Root cause.** The selector matches, so the endpoint exists. It just points at port 80. The image is `nginx-unprivileged`: it runs as uid 101, which can't bind ports below 1024, so it listens on **8080**. ingress-nginx gets `connection refused` and returns 502. Compare issue 6, where the controller has *no* endpoints and returns 503 itself.

**Fix.**
```
$ kubectl -n tickethub-broken patch svc tickethub-frontend --type=json -p '[{"op":"replace","path":"/spec/ports/0/targetPort","value":8080}]'
$ kubectl -n tickethub-broken get endpoints tickethub-frontend
tickethub-frontend   10.244.0.56:8080   3m14s
$ curl ... http://broken.tickethub.localtest.me:28080/
GET / -> 502 text/html        <-- still 502!
```

**Second-level investigation.** I didn't plan this part. The Service and EndpointSlice were correct, but the 502 continued for more than 60 seconds. I asked the controller directly what was in its dynamic upstream table:
```
$ kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --since=30s | grep broken | tail -2
... connect() failed (111: Connection refused) while connecting to upstream, ... upstream: "http://10.244.0.56:80/"

$ kubectl -n ingress-nginx exec deploy/ingress-nginx-controller -- curl -s localhost:10246/configuration/backends | ...
tickethub-broken-tickethub-frontend-80 [('10.244.0.56', '80')] 80
[{"name": "http", "protocol": "TCP", "port": 80, "targetPort": 80}]     <- stale Service spec
```
ingress-nginx was still holding the **old** Service spec. A change to the Service's `targetPort` alone had not triggered a resync of that backend. Touching the Ingress forced one:
```
$ kubectl -n tickethub-broken annotate ingress tickethub troubleshooting/resync="$(date +%s)" --overwrite
tickethub-broken-tickethub-frontend-80 [('10.244.0.56', '8080')] [{"name": "http", "protocol": "TCP", "port": 80, "targetPort": 8080}]
$ curl -s -o /dev/null -w "%{http_code}\n" http://broken.tickethub.localtest.me:28080/
200
```
Lesson: when the Kubernetes objects are correct and the traffic still isn't, check the controller's *view* of those objects.

## Issue 6: `503` on `/api/*` (Ingress points at a port the Service doesn't have)

```
$ curl -s -w "\nHTTP %{http_code}\n" http://broken.tickethub.localtest.me:28080/api/stats
<head><title>503 Service Temporarily Unavailable</title></head> ...
HTTP 503

$ kubectl -n tickethub-broken describe ingress tickethub | sed -n '/Rules:/,/Annotations:/p'
  broken.tickethub.localtest.me
                                 /api   tickethub-backend:8080 ()
                                 /      tickethub-frontend:80 (10.244.0.56:8080)
$ kubectl -n tickethub-broken get svc tickethub-backend
tickethub-backend   ClusterIP   10.96.165.250   <none>        8000/TCP   5m10s
```

**Root cause.** `describe ingress` shows `tickethub-backend:8080 ()`. The empty parentheses mean no endpoints were resolved, because the Service only exposes **8000**. With nothing to route to, the controller answers 503 itself.

**Fix.** I referenced the Service port **by name** (`http`), so renumbering the port can never break the Ingress again. The Helm chart and the raw manifests already do this.
```
$ kubectl -n tickethub-broken patch ingress tickethub --type=json -p '[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/port","value":{"name":"http"}}]'
$ curl -s -w "\nHTTP %{http_code}\n" http://broken.tickethub.localtest.me:28080/api/stats
{"total":0,"open":0,"in_progress":0,"resolved":0,"closed":0,"urgent_open":0}
HTTP 200
$ curl -s -w '\nHTTP %{http_code}\n' -X POST http://broken.tickethub.localtest.me:28080/api/tickets -H 'content-type: application/json' -d '{"subject":"Troubleshooting verified","requester":"sre@corp.example","priority":"LOW"}'
{"id":1,"subject":"Troubleshooting verified",...,"status":"OPEN","team":"L1 Support",...}
HTTP 201
```

## Issue 7: HPA stuck at `cpu: <unknown>` (no resource requests)

```
$ kubectl -n tickethub-broken get hpa tickethub-backend
tickethub-backend   Deployment/tickethub-backend   cpu: <unknown>/70%   1         3         1          5m24s

$ kubectl -n tickethub-broken describe hpa tickethub-backend | sed -n '/^Conditions:/,$p'
  ScalingActive  False   FailedGetResourceMetric  the HPA was unable to compute the replica count: failed to get cpu utilization: missing request for cpu in container backend of Pod tickethub-backend-67d6db5695-4hztw

$ kubectl top pod -n tickethub-broken
tickethub-backend-67d6db5695-4hztw    5m           86Mi
$ kubectl -n tickethub-broken get deploy tickethub-backend -o jsonpath='{.spec.template.spec.containers[0].resources}'
{}
```

**Root cause.** metrics-server is working: `kubectl top` returns numbers. But a `Utilization` target is *usage ÷ request*, and the container declares no request, so there is nothing to divide by. The HPA can't compute a percentage and will never scale.

**Fix / verify.**
```
$ kubectl -n tickethub-broken set resources deploy/tickethub-backend -c backend --requests=cpu=50m,memory=128Mi --limits=cpu=500m,memory=256Mi
$ kubectl -n tickethub-broken set resources deploy/tickethub-backend -c migrate --requests=cpu=50m,memory=128Mi --limits=cpu=500m,memory=256Mi
$ kubectl -n tickethub-broken get hpa tickethub-backend
tickethub-backend   Deployment/tickethub-backend   cpu: 12%/70%   1         3         1          6m6s
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
```

---

## Final verification: the fixed manifest matches what is running

I committed the seven live fixes to [`fixed-stack.yaml`](fixed-stack.yaml) and applied it over the patched namespace. Only the objects I had patched imperatively show `configured`. Everything else is `unchanged`, which shows the file describes the repaired state.

```
$ diff -u troubleshooting/broken-stack.yaml troubleshooting/fixed-stack.yaml | grep -E '^[-+] '   (20 changed lines, see evidence)
$ kubectl apply -f troubleshooting/fixed-stack.yaml
configmap/tickethub-config configured
persistentvolumeclaim/tickethub-postgres-data unchanged
deployment.apps/tickethub-postgres configured
service/tickethub-postgres unchanged
deployment.apps/tickethub-backend configured
service/tickethub-backend unchanged
deployment.apps/tickethub-frontend unchanged
service/tickethub-frontend configured
ingress.networking.k8s.io/tickethub configured
horizontalpodautoscaler.autoscaling/tickethub-backend unchanged

$ kubectl -n tickethub-broken get pods,endpoints,hpa
pod/tickethub-backend-79448dc7b7-87d68    1/1     Running   0          61s
pod/tickethub-frontend-6fffd56df7-jnzxq   1/1     Running   0          6m26s
pod/tickethub-postgres-6db7f7c9ff-g4nrd   1/1     Running   0          5m33s
endpoints/tickethub-backend    10.244.0.63:8000
endpoints/tickethub-frontend   10.244.0.56:8080
endpoints/tickethub-postgres   10.244.0.59:5432
horizontalpodautoscaler.autoscaling/tickethub-backend   Deployment/tickethub-backend   cpu: 10%/70%   1   3   1

GET /          -> 200
GET /api/stats -> 200
{"service":"TicketHub API","version":"0b9665e","environment":"troubleshooting","pod":"tickethub-backend-79448dc7b7-87d68","default_team":"L1 Support"}
```

## Real incidents found while building the project

These weren't planted. They happened during the build and are documented with evidence in the main README:

| Incident | Symptom | Root cause | Fix |
|---|---|---|---|
| Frontend `CrashLoopBackOff` after a node restart | `OOMKilled` (exit 137), then startup-probe failures | `worker_processes auto` started one nginx worker per **host** CPU (15) inside a 64Mi limit | pin `worker_processes 2` in the image, limit 96Mi |
| Grafana restarting, pegging ~10 CPU cores | 2/3 Ready, exit 137 | 256Mi limit too small; Go GC thrashing at the limit | `GOMAXPROCS=2`, `GOMEMLIMIT`, 512Mi limit ([evidence](../evidence/monitoring-02-grafana-resource-fix.txt)) |
| A 502 during `helm upgrade` | 1 of 120 requests failed mid-rollout | pod exits before ingress-nginx drops its endpoint | `lifecycle.preStop: sleep 5s` ([evidence](../evidence/helm-03-zero-downtime-rollout.txt)) |
| HPA reported `memory: 89%/85%` at idle | would scale out with no traffic | 96Mi request below the API's ~85Mi idle footprint | request 128Mi |
| Security gate closed on CI run 37633166811 | Gitleaks `generic-api-key` | fake `sg-…` id printed by the AWS emulator in an evidence file | narrow allowlist regex ([evidence](../evidence/security-02-gitleaks-false-positive.txt)) |
