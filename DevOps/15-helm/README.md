# Helm — Homework

Session 15. What Helm is, how a chart is built, and the full release lifecycle —
install, upgrade, rollback, and what happens when an upgrade fails.

The chart in [`notes-chart/`](notes-chart/) was **written by hand**, not scaffolded,
so every template in it is deliberate. Command results are **real captured
output** from the three-node kind cluster built in
[session 09](../09-kubernetes-fundamentals/README.md).

```bash
$ helm version
version.BuildInfo{Version:"v4.3.0", GitCommit:"bec5b06ed841fe5269972d864d5177944fd5970f", GitTreeState:"clean", GoVersion:"go1.27.1", KubeClientVersion:"v1.37"}
```

---

## Task 1 — What Helm actually solves

By session 14 this repository had accumulated dozens of near-identical YAML
files. The problems that causes are all the same problem:

1. **Environments differ only slightly.** dev wants 1 replica, prod wants 3 and
   an HPA. Copying the whole manifest set per environment means every future fix
   has to be made in every copy.
2. **A release is not an object.** `kubectl apply -f .` gives no way to ask
   "what is currently deployed?", and no way to undo it.
3. **`kubectl delete -f` only deletes what is still in the directory.** Remove a
   file, and the object it created is orphaned in the cluster forever.

Helm answers all three:

```
   chart  =  templates  +  default values          (the reusable package)
   release =  chart  +  your values  +  a name     (one deployment of it)
```

Helm is **a templating engine plus a release database**. The second half is the
part people forget, and it is what makes `rollback` possible.

---

## Task 2 — Chart structure

`helm create` scaffolds a chart with a lot of machinery in it:

```bash
$ helm create demo-chart
Creating demo-chart

$ find demo-chart -type f | sort
demo-chart/.helmignore
demo-chart/Chart.yaml
demo-chart/templates/NOTES.txt
demo-chart/templates/_helpers.tpl
demo-chart/templates/deployment.yaml
demo-chart/templates/hpa.yaml
demo-chart/templates/httproute.yaml
demo-chart/templates/ingress.yaml
demo-chart/templates/service.yaml
demo-chart/templates/serviceaccount.yaml
demo-chart/templates/tests/test-connection.yaml
demo-chart/values.yaml
```

The chart used for the rest of this assignment was written from scratch instead,
because reading generated boilerplate teaches much less than writing it:

```
notes-chart/
├── Chart.yaml              metadata: name, version, appVersion
├── values.yaml             default configuration
├── values-prod.yaml        production overrides
└── templates/
    ├── _helpers.tpl        shared snippets (leading _ = not a manifest)
    ├── configmap.yaml
    ├── deployment.yaml
    ├── service.yaml
    ├── hpa.yaml            rendered only when autoscaling.enabled
    └── NOTES.txt           printed after install
```

Two naming rules matter: **files starting with `_` are never rendered as
Kubernetes objects** (they hold reusable definitions), and **`NOTES.txt` is
templated but printed to the user** rather than applied.

---

## Task 3 — `Chart.yaml`

```yaml
apiVersion: v2
name: notes-app
description: A small notes web app used to learn Helm packaging, templating and releases
type: application

# version      = the version of THIS CHART. Bump it when the templates change.
# appVersion   = the version of the APPLICATION inside. Independent of the above.
version: 0.1.0
appVersion: "1.27"
```

The distinction that gets asked about in interviews:

| Field | Versions | Bumped when |
|---|---|---|
| `version` | the **chart** (packaging) | you change templates or defaults |
| `appVersion` | the **application** | you ship new application code |

They move independently: fixing a typo in a template bumps `version` only;
shipping nginx 1.28 with identical templates bumps `appVersion` only.
`apiVersion: v2` means Helm 3+ (v1 was Helm 2, with Tiller).

---

## Task 4 — `values.yaml` and layered overrides

```yaml
replicaCount: 1

image:
  repository: nginx
  tag: "1.27-alpine"
  pullPolicy: IfNotPresent

config:
  environment: development
  logLevel: debug
  welcomeMessage: "Notes App - development"

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70
```

`values-prod.yaml` lists **only the differences** — this is the whole point:

```yaml
replicaCount: 3

config:
  environment: production
  logLevel: warn
  welcomeMessage: "Notes App - PRODUCTION"

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 60
```

Values merge in increasing order of precedence:

```
  values.yaml  <  -f values-prod.yaml  <  --set key=value
```

Merging is **deep for maps but replacing for lists** — a frequent surprise, since
overriding one element of an array replaces the whole array.

---

## Task 5 — Templates

### Helpers

Repeated logic lives in `_helpers.tpl` and is pulled in with `include`:

```gotemplate
{{- define "notes-app.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

`trunc 63` is not decoration: Kubernetes object names are DNS labels with a
63-character limit, and `trimSuffix "-"` prevents a name ending in a hyphen after
truncation — which would be invalid.

Note the split between `notes-app.labels` and `notes-app.selectorLabels`. The
selector set is deliberately smaller and excludes `version`, because **a
Deployment's `selector` is immutable**: if a chart version appeared in the
selector, every chart bump would make `helm upgrade` fail outright.

### The three built-in objects

| Object | Holds | Used here for |
|---|---|---|
| `.Values` | merged values | everything configurable |
| `.Chart` | `Chart.yaml` | `.Chart.Name`, `.Chart.Version`, `.Chart.AppVersion` |
| `.Release` | this deployment | `.Release.Name`, `.Release.Revision`, `.Release.Service` |

### Conditionals

```gotemplate
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
```

`replicas` is **omitted entirely** when an HPA is managing the deployment.
Leaving it in would have Helm and the HPA fight over the replica count on every
upgrade — a genuinely common production bug.

The whole `hpa.yaml` is wrapped the same way, so the object only exists in
production.

### The checksum annotation

```gotemplate
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

Without this, changing only a ConfigMap value updates the ConfigMap and **leaves
the running pods untouched** — exactly the trap measured in
[session 12](../12-ingress-configmaps-secrets/README.md), where env vars never
refreshed. Hashing the rendered ConfigMap into a pod annotation changes the pod
template, which forces a rollout automatically.

### Linting and rendering without a cluster

```bash
$ helm lint notes-chart
==> Linting notes-chart
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

`helm template` renders locally — no cluster, no release, nothing applied:

```bash
$ helm template my-notes notes-chart | head -45
---
# Source: notes-app/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-notes-notes-app-config
  labels:
    app.kubernetes.io/name: notes-app
    app.kubernetes.io/instance: my-notes
    app.kubernetes.io/version: "1.27"
    app.kubernetes.io/managed-by: Helm
    helm.sh/chart: notes-app-0.1.0
    environment: development
data:
  ENVIRONMENT: "development"
  LOG_LEVEL: "debug"
  index.html: |
    <html>
      <body>
        <h1>Notes App - development</h1>
        <p>release: my-notes</p>
        <p>chart: notes-app-0.1.0</p>
        <p>appVersion: 1.27</p>
        <p>environment: development</p>
        <p>revision: 1</p>
      </body>
    </html>
```

The same chart with production values produces materially different output:

```bash
$ helm template my-notes notes-chart -f notes-chart/values-prod.yaml | grep -E 'replicas:|environment:|kind:|averageUtilization|cpu:|memory:'
kind: ConfigMap
    environment: production
        <p>environment: production</p>
kind: Service
    environment: production
kind: Deployment
    environment: production
              cpu: 500m
              memory: 256Mi
              cpu: 50m
              memory: 64Mi
kind: HorizontalPodAutoscaler
    environment: production
    kind: Deployment
          averageUtilization: 60
```

**An extra object appeared (`HorizontalPodAutoscaler`) and `replicas:` vanished
entirely** — the conditionals working, verified before anything touched the
cluster. `helm template | kubectl diff -f -` is the standard pre-flight check.

---

## Task 6 — Install

```bash
$ helm install my-notes notes-chart --wait --timeout 5m
NAME: my-notes
LAST DEPLOYED: Mon Sep 21 15:56:23 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
TEST SUITE: None
NOTES:
notes-app (0.1.0) has been deployed as release "my-notes".

  Environment : development
  Revision    : 1
  Replicas    : 1

Reach the app with:
  kubectl port-forward svc/my-notes-notes-app 8088:80
  curl http://localhost:8088
```

That `NOTES:` block is `NOTES.txt` rendered with this release's real values.

```bash
$ helm list
NAME    	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART          	APP VERSION
my-notes	default  	1       	2026-09-21 15:56:23.743782 +0530 IST	deployed	notes-app-0.1.0	1.27

$ kubectl get all -l app.kubernetes.io/instance=my-notes
NAME                                      READY   STATUS    RESTARTS   AGE
pod/my-notes-notes-app-66cd88d97b-snn86   1/1     Running   0          7s

NAME                         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
service/my-notes-notes-app   ClusterIP   10.96.60.206   <none>        80/TCP    7s

NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/my-notes-notes-app   1/1     1            1           7s
```

The app serves its own release metadata, which makes every later step verifiable
from outside:

```bash
$ curl http://localhost:8088
<html>
  <body>
    <h1>Notes App - development</h1>
    <p>release: my-notes</p>
    <p>chart: notes-app-0.1.0</p>
    <p>appVersion: 1.27</p>
    <p>environment: development</p>
    <p>revision: 1</p>
  </body>
</html>
```

---

## Task 7 — Upgrade

### Revision 2 — a one-flag change

```bash
$ helm upgrade my-notes notes-chart --set replicaCount=3 --wait --timeout 5m
Release "my-notes" has been upgraded. Happy Helming!
NAME: my-notes
REVISION: 2
DESCRIPTION: Upgrade complete
...
  Replicas    : 3

$ kubectl get deploy my-notes-notes-app
NAME                 READY   UP-TO-DATE   AVAILABLE   AGE
my-notes-notes-app   3/3     3            3           41s
```

### Revision 3 — switch the whole environment

```bash
$ helm upgrade my-notes notes-chart -f notes-chart/values-prod.yaml --wait --timeout 5m
Release "my-notes" has been upgraded. Happy Helming!
REVISION: 3
...
  Environment : production
  Revision    : 3
  Replicas    : autoscaled 3-10
```

```bash
$ kubectl get deploy,hpa -l app.kubernetes.io/instance=my-notes
NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/my-notes-notes-app   3/3     3            3           55s

NAME                                                     REFERENCE                       TARGETS              MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/my-notes-notes-app   Deployment/my-notes-notes-app   cpu: <unknown>/60%   3         10        1          13s
```

**An HPA that did not exist before now does**, created by the same chart with
different values. And the running application confirms the config actually
reached the pods:

```bash
$ curl http://localhost:8088
<html>
  <body>
    <h1>Notes App - PRODUCTION</h1>
    ...
    <p>environment: production</p>
    <p>revision: 3</p>
  </body>
</html>
```

The page changed because the checksum annotation forced a rollout. Without it,
the ConfigMap would have been updated and the old pods would still be serving
"development".

```bash
$ helm history my-notes
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION
1       	Mon Sep 21 15:56:23 2026	superseded	notes-app-0.1.0	1.27       	Install complete
2       	Mon Sep 21 15:56:45 2026	superseded	notes-app-0.1.0	1.27       	Upgrade complete
3       	Mon Sep 21 15:57:05 2026	deployed  	notes-app-0.1.0	1.27       	Upgrade complete
```

---

## Task 8 — Rollback

```bash
$ helm rollback my-notes 1 --wait --timeout 5m
Rollback was a success! Happy Helming!
```

```bash
$ kubectl get deploy,hpa -l app.kubernetes.io/instance=my-notes
NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/my-notes-notes-app   1/1     1            1           77s
```

Back to 1 replica, **and the HPA is gone** — rollback removes objects that the
target revision did not contain, which plain `kubectl apply` could never do.

```bash
$ curl http://localhost:8088
    <h1>Notes App - development</h1>
    <p>environment: development</p>
    <p>revision: 1</p>
```

```bash
$ helm history my-notes
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION
1       	Mon Sep 21 15:56:23 2026	superseded	notes-app-0.1.0	1.27       	Install complete
2       	Mon Sep 21 15:56:45 2026	superseded	notes-app-0.1.0	1.27       	Upgrade complete
3       	Mon Sep 21 15:57:05 2026	superseded	notes-app-0.1.0	1.27       	Upgrade complete
4       	Mon Sep 21 15:57:32 2026	deployed  	notes-app-0.1.0	1.27       	Rollback to 1
```

**Rolling back creates revision 4, described as "Rollback to 1".** History is
append-only — exactly the same semantics as `kubectl rollout undo` in
[session 10](../10-k8s-core-objects/README.md), but here it restores *values,
templates and the full object set*, not just a pod template.

---

## Task 9 — What a failed upgrade actually does

This is the part worth knowing before it happens in production.

```bash
$ helm upgrade my-notes notes-chart --set image.tag=does-not-exist --wait --timeout 45s
level=WARN msg="upgrade failed" name=my-notes error="resource Deployment/default/my-notes-notes-app not ready. status: InProgress, message: Pending termination: 1\ncontext deadline exceeded"
Error: UPGRADE FAILED: resource Deployment/default/my-notes-notes-app not ready. status: InProgress, message: Pending termination: 1
context deadline exceeded
```

```bash
$ helm history my-notes
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION
4       	Mon Sep 21 15:57:32 2026	deployed  	notes-app-0.1.0	1.27       	Rollback to 1
5       	Mon Sep 21 15:57:44 2026	failed    	notes-app-0.1.0	1.27       	Upgrade "my-notes" failed: resource Deployment/default/my-notes-notes-app not ready...
```

```bash
$ kubectl get pods -l app.kubernetes.io/instance=my-notes
NAME                                  READY   STATUS             RESTARTS   AGE
my-notes-notes-app-66cd88d97b-vg7pz   1/1     Running            0          57s
my-notes-notes-app-96f86bdf7-4s2j5    0/1     ImagePullBackOff   0          45s
```

**The cluster is left in a mixed state.** One healthy old pod, one broken new
pod, and a release marked `failed`. Helm did **not** clean up after itself. The
old pods survived only because the Deployment's own `maxUnavailable` protected
them — that is Kubernetes, not Helm.

### `--atomic` fixes this

```bash
$ helm upgrade my-notes notes-chart --set image.tag=does-not-exist --atomic --wait --timeout 45s
Flag --atomic has been deprecated, use --rollback-on-failure instead
Error: UPGRADE FAILED: release my-notes failed, and has been rolled back due to rollback-on-failure being set: resource Deployment/default/my-notes-notes-app not ready...
```

Two things in that output. First, **Helm 4 renamed the flag to
`--rollback-on-failure`**; `--atomic` still works but warns. Second, the message
now says *"and has been rolled back"*.

```bash
$ kubectl get pods -l app.kubernetes.io/instance=my-notes
NAME                                  READY   STATUS        RESTARTS   AGE
my-notes-notes-app-66cd88d97b-vg7pz   1/1     Running       0          114s
my-notes-notes-app-c7b76bf4-v7tjd     0/1     Terminating   0          45s
```

The broken pod is already `Terminating` — nobody had to intervene.

```bash
$ helm history my-notes
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION
5       	Mon Sep 21 15:57:44 2026	failed    	notes-app-0.1.0	1.27       	Upgrade "my-notes" failed: ...
6       	Mon Sep 21 15:58:40 2026	superseded	notes-app-0.1.0	1.27       	Rollback to 4
7       	Mon Sep 21 15:58:41 2026	failed    	notes-app-0.1.0	1.27       	Upgrade "my-notes" failed: ...
8       	Mon Sep 21 15:59:26 2026	deployed  	notes-app-0.1.0	1.27       	Rollback to 6

$ helm list
NAME    	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART          	APP VERSION
my-notes	default  	8       	2026-09-21 15:59:26.212768 +0530 IST	deployed	notes-app-0.1.0	1.27
```

Revision 7 failed and Helm **itself** created revision 8 to undo it, leaving the
release `deployed` rather than `failed`. **`--atomic`/`--rollback-on-failure`
plus `--timeout` should be the default in any CI pipeline** — without them a
failed deploy leaves broken pods and a `failed` release that blocks the next
upgrade.

---

## Task 10 — Packaging and repositories

```bash
$ helm package notes-chart -d ./helmwork
Successfully packaged chart and saved it to: .../helmwork/notes-app-0.1.0.tgz

$ ls -la helmwork/*.tgz
-rw-r--r--@ 1 shauryaverma  wheel  2512 Sep 21 15:59 .../notes-app-0.1.0.tgz

$ tar tzf helmwork/notes-app-0.1.0.tgz
notes-app/Chart.yaml
notes-app/values.yaml
notes-app/templates/NOTES.txt
notes-app/templates/_helpers.tpl
notes-app/templates/configmap.yaml
notes-app/templates/deployment.yaml
notes-app/templates/hpa.yaml
notes-app/templates/service.yaml
notes-app/values-prod.yaml
```

A chart is just a gzipped tarball — 2.5 KB here — named
`<name>-<version>.tgz` from `Chart.yaml`. A chart repository is nothing more than
a web server holding these plus an `index.yaml`.

```bash
$ helm repo add bitnami https://charts.bitnami.com/bitnami
"bitnami" has been added to your repositories

$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "bitnami" chart repository
Update Complete. ⎈Happy Helming!⎈

$ helm search repo bitnami/nginx --versions | head -5
NAME                            	CHART VERSION	APP VERSION	DESCRIPTION
bitnami/nginx                   	25.1.14      	1.31.6     	NGINX Open Source is a web server that can be a...
bitnami/nginx                   	25.1.13      	1.31.6     	NGINX Open Source is a web server that can be a...
bitnami/nginx                   	25.1.12      	1.31.6     	NGINX Open Source is a web server that can be a...
bitnami/nginx                   	25.1.11      	1.31.5     	NGINX Open Source is a web server that can be a...
```

Chart version `25.1.14` against app version `1.31.6` — the independence of those
two numbers, in the wild.

---

## Task 11 — Deploying a real third-party application

```bash
$ helm install web bitnami/nginx --version 25.1.14 \
    --set service.type=ClusterIP --set replicaCount=1 --set resourcesPreset=nano \
    --wait --timeout 6m
NAME: web
STATUS: deployed
REVISION: 1
NOTES:
CHART NAME: nginx
CHART VERSION: 25.1.14
APP VERSION: 1.31.6

⚠ WARNING: Since August 28th, 2025, only a limited subset of images/charts are available for free.
    Subscribe to Bitnami Secure Images to receive continued support and security updates.
```

```bash
$ kubectl get pods,svc -l app.kubernetes.io/instance=web
NAME                             READY   STATUS    RESTARTS   AGE
pod/web-nginx-6476798679-xqrh7   1/1     Running   0          19s

NAME                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
service/web-nginx   ClusterIP   10.96.220.51   <none>        80/TCP,443/TCP   20s
```

A production-grade application deployed in one command, with three values
overridden and no YAML written at all.

**`--version 25.1.14` is not optional in practice.** Without it, Helm installs
whatever is latest today, so the same command produces different results next
week. Pinning chart versions is the Helm equivalent of a lockfile.

The licensing warning is a useful real-world lesson too: charts from a public
repository are a **supply-chain dependency**, with the same terms-of-service and
security considerations as any other.

---

## Task 12 — Where Helm keeps its state

```bash
$ helm get values my-notes
USER-SUPPLIED VALUES:
null

$ helm get values my-notes --all | head -20
COMPUTED VALUES:
autoscaling:
  enabled: false
  maxReplicas: 5
  minReplicas: 1
  targetCPUUtilizationPercentage: 70
config:
  environment: development
  logLevel: debug
  welcomeMessage: Notes App - development
image:
  pullPolicy: IfNotPresent
  repository: nginx
  tag: 1.27-alpine
...
```

`helm get values` shows only what **you** supplied (here `null`, since revision 1
used pure defaults); `--all` shows the full merged result. Both matter when
debugging "why is this setting not taking effect".

```bash
$ helm get manifest my-notes | grep -E '^kind:|^  name:'
kind: ConfigMap
  name: my-notes-notes-app-config
kind: Service
  name: my-notes-notes-app
kind: Deployment
  name: my-notes-notes-app
```

The exact YAML currently applied — the authoritative answer to "what is actually
deployed".

### The release database is just Secrets

```bash
$ kubectl get secrets -l owner=helm --sort-by=.metadata.name
NAME                             TYPE                 DATA   AGE
sh.helm.release.v1.my-notes.v1   helm.sh/release.v1   1      4m13s
sh.helm.release.v1.my-notes.v2   helm.sh/release.v1   1      3m51s
sh.helm.release.v1.my-notes.v3   helm.sh/release.v1   1      3m31s
sh.helm.release.v1.my-notes.v4   helm.sh/release.v1   1      3m4s
sh.helm.release.v1.my-notes.v5   helm.sh/release.v1   1      2m52s
sh.helm.release.v1.my-notes.v6   helm.sh/release.v1   1      116s
sh.helm.release.v1.my-notes.v7   helm.sh/release.v1   1      115s
sh.helm.release.v1.my-notes.v8   helm.sh/release.v1   1      70s
sh.helm.release.v1.web.v1        helm.sh/release.v1   1      32s
```

**One Secret per revision**, of a custom type `helm.sh/release.v1`, holding the
gzipped rendered manifests and values. That is the entire "release database" —
Helm 3 has no server-side component at all, which is precisely what was wrong
with Helm 2's Tiller (a cluster-admin pod that everyone could reach).

Three consequences worth knowing: RBAC on Secrets controls who can see release
history; deleting these Secrets destroys the ability to roll back; and a release
lives in **one namespace**, so the same release name can exist independently in
several.

---

## Task 13 — Uninstall

```bash
$ helm uninstall web
release "web" uninstalled

$ kubectl get pods,svc -l app.kubernetes.io/instance=web
NAME                             READY   STATUS        RESTARTS   AGE
pod/web-nginx-6476798679-xqrh7   1/1     Terminating   0          31s

$ helm list
NAME    	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART          	APP VERSION
my-notes	default  	8       	2026-09-21 15:59:26.212768 +0530 IST	deployed	notes-app-0.1.0	1.27
```

Everything the release created is removed — including the Service, which no
`kubectl delete -f` against a partially-edited directory would have caught. Note
`helm uninstall` also deletes the history Secrets, so rollback is no longer
possible unless `--keep-history` was passed.

---

## Task 14 — The remaining commands: `helm status`, `helm get`, `helm repo`, `helm search`

The spec's command list includes `helm status`, `helm get` (all of it, not
just `values`/`manifest`), `helm repo` and `helm search`, and the sections
above did not use all of them. They were captured on a single-node kind cluster
(`hw-legacy`) in namespace `s15-gap`, alongside the mini project below. A
separate repository config
(`HELM_REPOSITORY_CONFIG`/`HELM_REPOSITORY_CACHE` pointing at a scratch
directory) was used so that adding and removing repos did not touch anyone
else's Helm setup on this machine. Full transcript:
[`evidence/s15-status-get-repo-search-miniproject.txt`](evidence/s15-status-get-repo-search-miniproject.txt).

### `helm repo` — add, list, update, remove

```console
$ helm repo list
no repositories to show

$ helm repo add bitnami https://charts.bitnami.com/bitnami
"bitnami" has been added to your repositories

$ helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
"ingress-nginx" has been added to your repositories

$ helm repo list
NAME         	URL                                       
bitnami      	https://charts.bitnami.com/bitnami        
ingress-nginx	https://kubernetes.github.io/ingress-nginx

$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "ingress-nginx" chart repository
...Successfully got an update from the "bitnami" chart repository
Update Complete. ⎈Happy Helming!⎈

$ helm repo remove ingress-nginx
"ingress-nginx" has been removed from your repositories

$ helm repo list
NAME   	URL                               
bitnami	https://charts.bitnami.com/bitnami
```

A repo is a named URL plus a locally cached `index.yaml`. `update` refreshes
that cache. Nothing is installed in the cluster by any of these commands.

### `helm search repo` vs `helm search hub`

```console
$ helm search repo nginx --max-col-width 45 | head -6
NAME                            	CHART VERSION	APP VERSION	DESCRIPTION                                  
bitnami/nginx                   	25.2.1       	1.31.6     	NGINX Open Source is a web server that can...
bitnami/nginx-ingress-controller	12.0.7       	1.13.1     	NGINX Ingress Controller is an Ingress con...
bitnami/nginx-intel             	2.1.15       	0.4.9      	DEPRECATED NGINX Open Source for Intel is ...
ingress-nginx/ingress-nginx     	4.15.1       	1.15.1     	Ingress controller for Kubernetes using NG...

$ helm search repo bitnami/redis --versions | head -4
NAME                 	CHART VERSION	APP VERSION	DESCRIPTION                                       
bitnami/redis        	28.3.1       	8.10.2     	Redis(R) is an open source, advanced key-value ...
bitnami/redis        	28.3.0       	8.10.2     	Redis(R) is an open source, advanced key-value ...
bitnami/redis        	28.2.4       	8.10.2     	Redis(R) is an open source, advanced key-value ...

$ helm search hub ingress-nginx --max-col-width 60 | head -5
URL                                                         	CHART VERSION	APP VERSION	DESCRIPTION                                                 
https://artifacthub.io/packages/helm/quench-ingress-nginx...	0.0.10       	1.15.10    	Ingress NGINX Controller: the Kubernetes-maintained Ingre...
https://artifacthub.io/packages/helm/ingress-nginx/ingres...	4.15.1       	1.15.1     	Ingress controller for Kubernetes using NGINX as a revers...
https://artifacthub.io/packages/helm/ingress-nginx-intern...	4.1.0        	1.2.0      	Ingress controller for Kubernetes using NGINX as a revers...

$ helm show chart ingress-nginx/ingress-nginx | head -12
apiVersion: v2
appVersion: 1.15.1
description: Ingress controller for Kubernetes using NGINX as a reverse proxy and
  load balancer
home: https://github.com/kubernetes/ingress-nginx
...
```

- **`search repo`** searches only the repos added locally, using the cached
  indexes. It works offline and is limited to what you have added.
  `--versions` lists every published chart version, which you need in order to
  pin `--version`.
- **`search hub`** queries Artifact Hub, the public index of thousands of
  repos. It returns URLs, not installable `repo/chart` names, so you still
  have to `repo add` the right repo. Searching `ingress-nginx` there also
  returns forks and lookalikes next to the official chart, so check the
  publisher before installing.
- `helm show chart|values|readme` inspects a chart before installing it.

### `helm status` — the release plus its live resources

```console
$ helm status notes-dev -n s15-gap
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 19:09:12 2026
NAMESPACE: s15-gap
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
RESOURCES:
==> v1/ConfigMap
NAME                         DATA   AGE
notes-dev-notes-app-config   3      7s

==> v1/Service
NAME                  TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
notes-dev-notes-app   ClusterIP   10.96.20.181   <none>        80/TCP    7s

==> v1/Deployment
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
notes-dev-notes-app   1/1     1            1           7s

==> v1/Pod(related)
NAME                                   READY   STATUS    RESTARTS   AGE
notes-dev-notes-app-68f875f899-blwx6   1/1     Running   0          7s

TEST SUITE: None
NOTES:
notes-app (0.1.0) has been deployed as release "notes-dev".
...
```

`status` combines Helm's record (revision, status, description, NOTES) with a
live `kubectl get` of every object the release owns, including related pods.
After `uninstall` it returns `Error: release: not found`.

### `helm get` — everything Helm stored for a revision

```console
$ helm get values notes-dev -n s15-gap
USER-SUPPLIED VALUES:
null

$ helm get values notes-dev -n s15-gap --all | head -12
COMPUTED VALUES:
autoscaling:
  enabled: false
  maxReplicas: 5
  minReplicas: 1
  targetCPUUtilizationPercentage: 70
config:
  environment: development
  logLevel: debug
  welcomeMessage: Notes App - development
image:
  pullPolicy: IfNotPresent

$ helm get metadata notes-dev -n s15-gap
NAME: notes-dev
CHART: notes-app
VERSION: 0.1.0
APP_VERSION: 1.27
LABELS: modifiedAt=1791380359,name=notes-dev,owner=helm,status=deployed,version=1
NAMESPACE: s15-gap
REVISION: 1
STATUS: deployed
DEPLOYED_AT: 2026-10-07T19:09:12+05:30
APPLY_METHOD: server-side apply

$ helm get notes notes-dev -n s15-gap
NOTES:
notes-app (0.1.0) has been deployed as release "notes-dev".
  Environment : development
  Revision    : 1
  Replicas    : 1
...

$ helm get hooks notes-dev -n s15-gap
                                   (empty: this chart defines no hooks)

$ helm get manifest notes-dev -n s15-gap | grep -E '^# Source|^kind:'
# Source: notes-app/templates/configmap.yaml
kind: ConfigMap
# Source: notes-app/templates/service.yaml
kind: Service
# Source: notes-app/templates/deployment.yaml
kind: Deployment

$ helm get all notes-dev -n s15-gap | grep -E '^NAME:|^LAST DEPLOYED:|^STATUS:|^REVISION:|^COMPUTED VALUES|^HOOKS|^MANIFEST|^NOTES|^# Source'
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 19:09:12 2026
STATUS: deployed
REVISION: 1
COMPUTED VALUES:
HOOKS:
MANIFEST:
# Source: notes-app/templates/configmap.yaml
# Source: notes-app/templates/service.yaml
# Source: notes-app/templates/deployment.yaml
NOTES:
```

| `helm get …` | Returns |
|---|---|
| `values` | only the values **you** supplied (`null` for a plain install), `--all` for the merged result |
| `manifest` | the exact rendered YAML that was applied |
| `notes` | the rendered `NOTES.txt` |
| `hooks` | rendered hook resources (none in this chart) |
| `metadata` | chart, versions, revision, status, apply method (Helm 4 uses server-side apply) |
| `all` | all of the above in one document |

Every subcommand accepts `--revision N`. In the mini project below,
`helm get values --revision 2` shows exactly what a rollback would restore.

---

## Mini project — the course's notes-chart flow, step by step

The course mini project (`devops-heros/session-15-helm/mini-project/`) builds a
`notes-chart` with `values.yaml`, `values-prod.yaml` and
deployment/service/configmap templates. It then runs lint → template → install
(dev) → upgrade (prod) → history → **bad upgrade** → **rollback to revision 2** →
uninstall. My [`notes-chart/`](notes-chart/) is that project, extended with
helpers, `NOTES.txt`, an HPA and a checksum annotation. Its pieces are
described in Tasks 2–5 above. Here is the whole course flow, run in order on
`hw-legacy`:

| Course step | Command | Result |
|---|---|---|
| 8 Lint | `helm lint notes-chart` | `1 chart(s) linted, 0 chart(s) failed` (only an "icon is recommended" info) |
| 9 Render | `helm template notes-dev notes-chart` | ConfigMap, Service, Deployment with `replicas: 1`, `nginx:1.27-alpine` |
| 10 Install | `helm install notes-dev notes-chart --wait` | revision 1, 1 pod, page says *development / revision 1* |
| 11 Upgrade to prod | `helm upgrade … -f notes-chart/values-prod.yaml --wait` | revision 2, 3 pods + HPA, page says *PRODUCTION / revision 2* |
| 12 History | `helm history notes-dev` | 1 superseded, 2 deployed |
| 13 Bad upgrade | `helm upgrade … --set image.tag=broken-tag-does-not-exist` | revision 3 **`deployed`**, but a new pod in `ImagePullBackOff` |
| 14 Rollback | `helm rollback notes-dev 2 --wait` | revision 4 "Rollback to 2", broken pod Terminating, 3/3 healthy |
| 15 Clean up | `helm uninstall notes-dev` | all objects removed, `helm status` → `release: not found` |

### Install, then upgrade to production values

```console
$ helm install notes-dev notes-chart -n s15-gap --wait --timeout 3m
NAME: notes-dev
STATUS: deployed
REVISION: 1

$ kubectl -n s15-gap exec client -- wget -q -O- http://notes-dev-notes-app
    <h1>Notes App - development</h1>
    <p>environment: development</p>
    <p>revision: 1</p>

$ helm upgrade notes-dev notes-chart -f notes-chart/values-prod.yaml -n s15-gap --wait --timeout 3m
Release "notes-dev" has been upgraded. Happy Helming!
STATUS: deployed
REVISION: 2

$ kubectl -n s15-gap get deploy,hpa -l app.kubernetes.io/instance=notes-dev
NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/notes-dev-notes-app   3/3     3            3           20s

NAME                                                      REFERENCE                        TARGETS              MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/notes-dev-notes-app   Deployment/notes-dev-notes-app   cpu: <unknown>/60%   3         10        1          12s

$ kubectl -n s15-gap exec client -- wget -q -O- http://notes-dev-notes-app
    <h1>Notes App - PRODUCTION</h1>
    <p>environment: production</p>
    <p>revision: 2</p>

$ helm history notes-dev -n s15-gap
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION     
1       	Wed Oct  7 19:09:12 2026	superseded	notes-app-0.1.0	1.27       	Install complete
2       	Wed Oct  7 19:09:19 2026	deployed  	notes-app-0.1.0	1.27       	Upgrade complete
```

### The bad upgrade — and why `helm status` says it is fine

Run exactly as the course does it, **without `--wait`**:

```console
$ helm upgrade notes-dev notes-chart -f notes-chart/values-prod.yaml --set image.tag=broken-tag-does-not-exist -n s15-gap
Release "notes-dev" has been upgraded. Happy Helming!
STATUS: deployed
REVISION: 3
DESCRIPTION: Upgrade complete

$ helm status notes-dev -n s15-gap          (30 s later)
STATUS: deployed
REVISION: 3
DESCRIPTION: Upgrade complete
RESOURCES:
==> v1/Deployment
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
notes-dev-notes-app   3/3     1            3           54s

==> v1/Pod(related)
NAME                                   READY   STATUS             RESTARTS   AGE
notes-dev-notes-app-86d54d8b5f-27nhc   1/1     Running            0          46s
notes-dev-notes-app-86d54d8b5f-ltq74   1/1     Running            0          46s
notes-dev-notes-app-86d54d8b5f-wwrh2   1/1     Running            0          40s
notes-dev-notes-app-bbdcc47bf-z2zbx    0/1     ImagePullBackOff   0          31s

$ helm get values notes-dev -n s15-gap     (excerpt)
image:
  tag: broken-tag-does-not-exist

$ kubectl -n s15-gap exec client -- wget -q -O- http://notes-dev-notes-app
    <h1>Notes App - PRODUCTION</h1>
    <p>environment: production</p>
    <p>revision: 2</p>
```

**Without `--wait`, Helm reports success as soon as the API server accepts
the objects.** Revision 3 is `deployed` and the description says "Upgrade
complete", yet the new pod can't pull its image. Only the resource list in
`helm status` gives it away (`UP-TO-DATE 1`, `ImagePullBackOff`). Users were
not affected: the Deployment's rolling update kept the three revision-2 pods,
which is why the page still says *revision 2*. Compare Task 9, where `--wait`
made the same mistake show up as a `failed` release.

### Rollback to revision 2

```console
$ helm rollback notes-dev 2 -n s15-gap --wait --timeout 3m
Rollback was a success! Happy Helming!

$ kubectl -n s15-gap get pods -l app.kubernetes.io/instance=notes-dev
NAME                                   READY   STATUS        RESTARTS   AGE
notes-dev-notes-app-86d54d8b5f-27nhc   1/1     Running       0          46s
notes-dev-notes-app-86d54d8b5f-ltq74   1/1     Running       0          46s
notes-dev-notes-app-86d54d8b5f-wwrh2   1/1     Running       0          40s
notes-dev-notes-app-bbdcc47bf-z2zbx    0/1     Terminating   0          31s

$ helm history notes-dev -n s15-gap
REVISION	UPDATED                 	STATUS    	CHART          	APP VERSION	DESCRIPTION     
1       	Wed Oct  7 19:09:12 2026	superseded	notes-app-0.1.0	1.27       	Install complete
2       	Wed Oct  7 19:09:19 2026	superseded	notes-app-0.1.0	1.27       	Upgrade complete
3       	Wed Oct  7 19:09:35 2026	superseded	notes-app-0.1.0	1.27       	Upgrade complete
4       	Wed Oct  7 19:10:06 2026	deployed  	notes-app-0.1.0	1.27       	Rollback to 2   

$ helm status notes-dev -n s15-gap        (NOTES section only)
NOTES:
notes-app (0.1.0) has been deployed as release "notes-dev".
  Environment : production
  Revision    : 2
  Replicas    : autoscaled 3-10

$ kubectl -n s15-gap exec client -- wget -q -O- http://notes-dev-notes-app
    <h1>Notes App - PRODUCTION</h1>
    <p>environment: production</p>
    <p>revision: 2</p>
```

The rollback deleted the broken pod. The ReplicaSet `86d54d8b5f` is the one
from revision 2, and its pods were never replaced. Helm records the rollback
as **revision 4**, but the NOTES and the page still say "Revision: 2". A
rollback re-applies the **stored** manifest of revision 2, so `.Release.Revision`
keeps its old rendered value. It does not render the templates again.

### Clean up

```console
$ helm uninstall notes-dev -n s15-gap
release "notes-dev" uninstalled

$ helm status notes-dev -n s15-gap
Error: release: not found

$ kubectl -n s15-gap get secrets -l owner=helm
No resources found in s15-gap namespace.
```

Uninstall also deleted the release-history Secrets (no `--keep-history`), so
nothing is left to roll back to. One Helm 4 detail: `helm list --all` returned
`Error: unknown flag: --all`. In Helm 4, `helm list` already shows releases in
every status by default, and status filters such as `--failed` and
`--uninstalled` replace the old `--all`.

### Task 2's rollback workflow, mapped

The spec's Install → Upgrade → Verify → Upgrade again → Verify → Rollback →
Verify sequence is Tasks 6–8 above (release `my-notes`), and the mini project
repeats it with a bad upgrade:

| Step | Tasks 6–8 (`my-notes`) | Mini project (`notes-dev`) |
|---|---|---|
| Install | rev 1, page *development / revision 1* | rev 1, same |
| Upgrade | rev 2, `--set replicaCount=3`, 3/3 ready | rev 2, prod values, 3 pods + HPA |
| Verify | `kubectl get deploy` 3/3 | page *PRODUCTION / revision 2* |
| Upgrade again | rev 3, prod values, HPA appears | rev 3, broken image tag |
| Verify | page *PRODUCTION / revision 3* | `ImagePullBackOff` despite `STATUS: deployed` |
| Rollback | `helm rollback my-notes 1` → rev 4 | `helm rollback notes-dev 2` → rev 4 |
| Verify | 1 replica, HPA gone, page *revision 1* | broken pod gone, 3/3, page *revision 2* |

---

## Command reference

| Command | Purpose |
|---|---|
| `helm create <name>` | scaffold a chart |
| `helm lint <chart>` | validate before deploying |
| `helm template <rel> <chart>` | render locally; no cluster needed |
| `helm install <rel> <chart>` | create release, revision 1 |
| `helm upgrade <rel> <chart>` | new revision |
| `helm upgrade -i` | install if absent, else upgrade — the CI-safe form |
| `helm history <rel>` | all revisions and their status |
| `helm rollback <rel> <n>` | revert (appends a new revision) |
| `helm get values <rel> [--all]` | supplied vs computed values |
| `helm get manifest <rel>` | the YAML actually applied |
| `helm uninstall <rel>` | remove everything |
| `helm package <chart>` | build the `.tgz` |
| `helm status <rel>` | release state + live resources + NOTES |
| `helm get notes\|hooks\|metadata\|all <rel>` | the other stored parts of a revision (`--revision N`) |
| `helm repo add\|list\|update\|remove` | manage chart repositories |
| `helm search repo <kw> [--versions]` | search added repos (local index) |
| `helm search hub <kw>` | search Artifact Hub |
| `helm show chart\|values <repo/chart>` | inspect a chart before installing |
| `--wait --timeout` | block until healthy |
| `--atomic` / `--rollback-on-failure` | auto-revert a failed upgrade |

---

## What I took away

- **Helm is a release database as much as a templating engine.** Templating
  alone is `helm template`; the value is the eight revision Secrets that made
  `rollback` possible.
- **A failed upgrade does not clean up after itself.** Proven: one healthy pod
  and one `ImagePullBackOff` pod left side by side, release marked `failed`.
  `--atomic` (now `--rollback-on-failure`) is what makes a deploy safe.
- **Rollback removes objects, not just fields.** Reverting to revision 1 deleted
  the HPA that revision 3 had created.
- **The checksum-annotation trick is essential**, not clever. Without it a
  config-only upgrade updates the ConfigMap and leaves the pods running the old
  values — the exact failure measured in session 12.
- **Never put a version in a Deployment's selector** — selectors are immutable,
  and a chart bump would break every future upgrade.
- **Omit `replicas` when an HPA is enabled**, or Helm and the autoscaler fight on
  every deploy.
- **Pin third-party chart versions.** `--version` is the difference between a
  reproducible deploy and one that changes silently next week.

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Understand what Helm is and why | Done — three concrete problems it solves, from this repo's own YAML sprawl |
| 2 | Understand chart structure | Done — `helm create` compared with a hand-written chart |
| 3 | `Chart.yaml` | Done — `version` vs `appVersion` distinguished |
| 4 | `values.yaml` | Done — defaults + prod overrides, precedence order explained |
| 5 | Templates | Done — helpers, conditionals, built-in objects, checksum annotation |
| 5 | Validate without a cluster | Done — `helm lint` clean, `helm template` diffed dev vs prod |
| 6 | Install a release | Done — revision 1, app serving its own release metadata |
| 7 | Upgrade a release | Done — revisions 2 and 3; an HPA appeared, page content changed |
| 8 | Rollback | Done — back to revision 1's state; HPA removed; history append-only |
| 9 | Handle a failed upgrade | Done — **mixed broken state reproduced**, then fixed with `--atomic` |
| 10 | Package a chart | Done — 2.5 KB `.tgz`, contents listed |
| 10 | Use a chart repository | Done — bitnami added, searched, versions compared |
| 11 | Deploy a real application | Done — `bitnami/nginx` 25.1.14 running, 3 values overridden |
| 12 | Understand release storage | Done — 9 `helm.sh/release.v1` Secrets, one per revision |
| 13 | Uninstall | Done — all objects removed, verified |
| 14 | `helm status` | Done — live resources shown, incl. an `ImagePullBackOff` pod under `STATUS: deployed` |
| 14 | `helm get` (values / manifest / notes / hooks / metadata / all) | Done — every subcommand captured |
| 14 | `helm repo` (add / list / update / remove) | Done — in an isolated repository config |
| 14 | `helm search` (repo / hub) | Done — local index vs Artifact Hub, `--versions` |
| — | Mini project (course notes-chart flow) | Done — lint → template → install → prod upgrade → bad upgrade → rollback 2 → uninstall |
