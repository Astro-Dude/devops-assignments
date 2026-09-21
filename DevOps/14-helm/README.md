# Helm — Homework

Session 15: package and deploy the Notes App, override values, upgrade, break,
roll back and uninstall. The course uses nginx as a stand-in for the Notes app;
this chart serves the nginx page rather than implementing a notes database.

Source: [course mini-project](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-15-helm/mini-project).
The [chart](notes-chart/) follows that exercise. All commands and real output are
in the [captured transcript](evidence/session.txt), including deliberate failures.
Tested using Helm 4.3.0 on `kind-devops-hw`, namespace `assignment14`.

## Chart structure and values

| File | Purpose |
|---|---|
| `Chart.yaml` | Chart metadata: application chart, version `0.1.0`, appVersion `1.0` |
| `values.yaml` | Development defaults: one replica, nginx `1.24`, development environment |
| `values-prod.yaml` | Production exercise override: three replicas, nginx `1.25`, production environment |
| `templates/deployment.yaml` | Renders replicas, image and environment label; imports ConfigMap environment |
| `templates/service.yaml` | NodePort Service on port 80, nodePort 30090 |
| `templates/configmap.yaml` | Provides `APP_NAME` and `ENVIRONMENT` |

A chart is a reusable package; `notes-dev` is one release of it. `.Values` supplies
configuration and `.Release.Name` keeps object names tied to a release. `quote`
ensures ConfigMap values render as strings. Chart `version` versions the package;
`appVersion` is descriptive and does not itself change the Deployment image.
The image is controlled by `image.repository` and `image.tag` here.

Values precedence is chart defaults, then `-f` overrides, then `--set` overrides.
Both default and production renders and lint results are preserved. Production
values here are an exercise profile, not a production security configuration.

## Executed lifecycle

1. Linted and rendered the chart with development and production values.
2. Installed `notes-dev` with readiness waiting. Checked resources, environment and
   an HTTP request through the Service from inside the cluster.
3. Upgraded with `values-prod.yaml`. Verified three ready replicas, nginx `1.25`,
   and `ENVIRONMENT=production`. Inspected effective values and release history.
4. Upgraded to `broken-tag-does-not-exist` without readiness waiting. Observed
   `ImagePullBackOff` and captured Events. A Helm revision marked deployed does
   not by itself mean all application Pods are healthy.
5. Rolled back explicitly to revision 2 with readiness waiting, restoring the
   production configuration. Rollback creates a new revision, preserving history.
6. Repeated a bad upgrade with automatic rollback and a 35-second timeout.
   The command failed as intended; release history and a successful HTTP request
   verify restoration of the healthy configuration.
7. Uninstalled the release. The immediate check showed the Deployment, Service
   and chart ConfigMap gone, with Pods still terminating or completed. Deleting
   the exercise namespace and waiting for completion finished cleanup, including
   its Kubernetes-provided root CA ConfigMap.

The installed Helm 4 uses `--rollback-on-failure` for the course's Helm 3
`--atomic` upgrade behavior. This was checked against CLI help and the
[Helm upgrade reference](https://helm.sh/docs/helm/helm_upgrade/).

## Run it yourself

Run from this folder with the cluster from [assignment 08](../08-kubernetes-fundamentals/README.md):

```bash
helm lint notes-chart
helm template notes-dev notes-chart -f notes-chart/values-prod.yaml
helm --kube-context kind-devops-hw -n assignment14 install notes-dev notes-chart --create-namespace --wait
helm --kube-context kind-devops-hw -n assignment14 upgrade notes-dev notes-chart -f notes-chart/values-prod.yaml --wait
helm --kube-context kind-devops-hw -n assignment14 history notes-dev
```

Follow the transcript for the deliberate failure, rollback and cleanup commands.
For browser access on macOS kind, use `kubectl --context kind-devops-hw -n assignment14
port-forward svc/notes-dev-svc 8090:80`, then open `http://localhost:8090`.
NodePort 30090 is not mapped onto the host in the existing kind configuration;
the captured HTTP checks use the cluster's internal Service DNS instead.

Changing ConfigMap environment alone does not restart existing Pods in this
course chart. The tested production upgrade changes the image and triggers a
rollout. For environment-only changes, trigger a rollout explicitly or add a
ConfigMap checksum annotation to the Pod template.

## Captured recovery evidence

The final history records the failed upgrade and the automatic rollback revision.
The HTTP request below was made after that rollback.

```text
$ helm --kube-context kind-devops-hw -n assignment14 history notes-dev
REVISION	UPDATED                 	STATUS    	CHART            	APP VERSION	DESCRIPTION
1       	Mon Sep 21 15:13:03 2026	superseded	notes-chart-0.1.0	1.0        	Install complete
2       	Mon Sep 21 15:14:15 2026	superseded	notes-chart-0.1.0	1.0        	Upgrade complete
3       	Mon Sep 21 15:15:01 2026	superseded	notes-chart-0.1.0	1.0        	Upgrade complete
4       	Mon Sep 21 15:15:18 2026	superseded	notes-chart-0.1.0	1.0        	Rollback to 2
5       	Mon Sep 21 15:15:18 2026	failed    	notes-chart-0.1.0	1.0        	Upgrade "notes-dev" failed: resource Deployment/assignment14/notes-dev-deploy not ready. status: InProgress, message: Updated: ...
6       	Mon Sep 21 15:15:53 2026	deployed  	notes-chart-0.1.0	1.0        	Rollback to 4
[exit 0]

$ kubectl --context kind-devops-hw -n assignment14 exec deploy/notes-dev-deploy -- curl -s -o /dev/null -w "HTTP %{http_code}\n" http://notes-dev-svc
HTTP 200
[exit 0]

```
