# Kubernetes Troubleshooting — Homework

Session 14, including the troubleshooting mini-project. Executed on the three-node
`kind-devops-hw` cluster in the isolated namespace `assignment13`.

Source: [course lab](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-14-kubernetes-troubleshooting).
The [complete captured transcript](evidence/session.txt) contains commands,
actual output, exit codes, diagnostics before changes, and verification after fixes.
The [manifests](manifests/) retain both broken and corrected configurations.
Do not apply the whole directory recursively: broken and fixed files deliberately
address the same resources. Run the files in the transcript's order.

## Investigation and fixes

| Problem | What I saw | Diagnostic command | Root cause | Fix and verification |
|---|---|---|---|---|
| Broken Pod / crash loop | `Error`, repeated restarts, `BackOff` Events, exit code 1 | `describe pod crash-demo`; `logs crash-demo --previous` | Startup command explicitly exits with `exit 1` | Replace the bare Pod with the fixed command; wait for Ready |
| Image problem | `ImagePullBackOff` | `describe pod image-demo`; Pod events | `nginx:this-image-does-not-exist` is not a valid tag | Apply the fixed image; wait for Ready |
| Pending Pod | Pending, `FailedScheduling` | `describe pod pending-demo` | Node selector names a node that does not exist | Recreate without the impossible selector; verify Ready |
| Mini-project broken Pod | `ImagePullBackOff` | `describe pod project-broken-pod` | `nginx:this-tag-does-not-exist` cannot be resolved | Change the tag to `1.27`; verify Ready |
| Service problem | DNS resolves but HTTP fails; no backend addresses | `describe svc`; `get pods --show-labels`; `get endpointslices` | Service selector `app: wrong-app` does not match `app: troubleshooting-app` | Restore selector, observe endpoint addresses, fetch nginx through the Service |
| DNS negative control | NXDOMAIN for a missing Service | `exec client -- nslookup ...` | Requested Service does not exist in the namespace | Use the actual Service FQDN, which resolves successfully |

The crashing container repeatedly exited with code 1 and generated `BackOff`
Events. A two-minute poll did not catch the transient `CrashLoopBackOff` waiting
state on this cluster; the displayed status remained `Error`. The transcript
preserves that observation instead of substituting the course’s expected output.

The healthy baseline proves nginx responds on localhost before changing anything.
After deliberately breaking the Service selector, DNS still resolves: a ClusterIP
Service record does not prove that ready backend Pods exist. After repair, the
same client fetches the nginx page through the Service. EndpointSlices are used
as the current endpoint API; the course uses the older Endpoints API.

## Mini-project: five answers

1. **Status:** the broken image Pod reached `ImagePullBackOff` after pull failures.
2. **Actual error:** the container runtime could not resolve the nonexistent nginx tag;
   the exact registry error is preserved in the Pod's Events in the transcript.
3. **Command that found it:** `kubectl describe pod project-broken-pod`.
4. **Wrong image:** its repository is nginx, but `this-tag-does-not-exist` is not a published tag.
5. **Fix:** replace that tag with the valid course tag `1.27`, recreate the Pod,
   then wait for readiness. Deleting without correcting the manifest only repeats the failure.

## README questions

1. **What does get show?** A current resource summary: readiness, displayed status,
   restart count and age; `-o wide` adds placement and addresses.
2. **get versus describe?** Get summarizes or returns structured API data; describe
   combines configuration, status, conditions and recent Events for diagnosis.
3. **Why logs?** Application stdout/stderr can explain exits that Kubernetes only
   records as failures. `--previous` retrieves the previous container instance.
4. **When exec?** When a container is running and I need to inspect files, environment,
   local HTTP or DNS from its network namespace. A crashing container may exit too quickly.
5. **CrashLoopBackOff?** Kubernetes is delaying another restart after repeated container
   exits; it is a symptom. Logs and termination state reveal the underlying cause.
6. **ImagePullBackOff?** Kubernetes is delaying another image-pull attempt. Check the
   tag, registry access, credentials and network; here the tag is wrong.
7. **Why Pending?** Scheduling or setup has not finished. Possible causes include
   resource shortages, taints, impossible selectors, unbound storage or image pulling.
   Events identify which applies; here the node selector is impossible.
8. **Why no Service endpoints?** No matching ready Pods, a selector mismatch, or an
   intentionally selectorless Service without manually managed endpoints.
9. **Selector and labels?** The selector identifies backend Pods by their labels in
   the same namespace. Similar names do not create a match.
10. **Kubernetes DNS?** Cluster DNS resolves Service names such as
    `troubleshooting-service.assignment13.svc.cluster.local` to their cluster addresses.
    Resolution and application connectivity must be tested separately.

## Reproduce and clean up

From this directory, use the commands in [the transcript](evidence/session.txt).
Every command explicitly targets `kind-devops-hw` and `assignment13`. The final
successful state is two ready nginx application Pods behind the repaired Service,
plus the repaired demonstration Pods. The final namespace deletion cleans up only
this assignment's resources. The existing cluster and other assignments remain available.

## Captured Service evidence

DNS resolved while the selector was broken. After restoring the selector,
EndpointSlices contained both backend addresses and the HTTP request succeeded.

```text
$ kubectl --context kind-devops-hw -n assignment13 exec client -- nslookup troubleshooting-service.assignment13.svc.cluster.local
Server:		10.96.0.10
Address:	10.96.0.10:53


Name:	troubleshooting-service.assignment13.svc.cluster.local
Address: 10.96.235.104

[exit 0]

$ kubectl --context kind-devops-hw -n assignment13 get endpointslices -l kubernetes.io/service-name=troubleshooting-service
NAME                            ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
troubleshooting-service-8wqx9   IPv4          80      10.244.1.87,10.244.2.71   3m40s
[exit 0]

$ kubectl --context kind-devops-hw -n assignment13 exec client -- wget -T 5 -q -O- http://troubleshooting-service
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }
</style>
</head>
<body>
<h1>Welcome to nginx!</h1>
<p>If you see this page, the nginx web server is successfully installed and
working. Further configuration is required.</p>

<p>For online documentation and support please refer to
<a href="http://nginx.org/">nginx.org</a>.<br/>
Commercial support is available at
<a href="http://nginx.com/">nginx.com</a>.</p>

<p><em>Thank you for using nginx.</em></p>
</body>
</html>
[exit 0]

```
