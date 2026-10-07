# Ingress vs Ingress Controller

Session 12, Task 4. What an Ingress is, what an Ingress Controller is, how they
differ, why you need both, and examples.

The explanation is backed by one experiment: **the same Ingress applied twice**.
The first time no controller claims it; the second time ingress-nginx does. All
output is **real captured output** from the single-node kind cluster
`hw-legacy`, with ingress-nginx v1.15.1 installed and kind mapping host port
**8080 → 80**. Manifests: [`app.yaml`](app.yaml),
[`ingress-no-controller.yaml`](ingress-no-controller.yaml),
[`ingress-nginx-class.yaml`](ingress-nginx-class.yaml). Full transcript:
[`../evidence/s12-ingress-vs-controller.txt`](../evidence/s12-ingress-vs-controller.txt).

---

## What is an Ingress?

An **Ingress** is a Kubernetes **API object**: a few lines of YAML that
describe HTTP(S) routing rules. "Requests for host `demo.s12.local`, path `/`,
go to Service `hello` port 80", plus optional TLS settings. It is a
**configuration request only**. On its own it runs nothing, opens no port and
forwards no packets. It is like a ticket in a queue that something still has
to act on.

```yaml
spec:
  ingressClassName: nginx          # which controller should implement this
  rules:
    - host: demo.s12.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: hello, port: { number: 80 } }
```

## What is an Ingress Controller?

An **Ingress Controller** is **running software**: a Deployment of real
reverse-proxy Pods (nginx, Traefik, HAProxy, Envoy, or a cloud load balancer
integration). It:

1. **watches** the API for Ingress objects of *its* IngressClass (plus
   Services, EndpointSlices and Secrets),
2. **translates** them into its own proxy configuration (here, `nginx.conf`),
3. **receives** the actual traffic on its own Service (LoadBalancer/NodePort)
   and proxies it to the Pod IPs,
4. **writes back** the Ingress's `status.loadBalancer` (the `ADDRESS` column).

The controller installed here:

```console
$ kubectl get ingressclass
NAME    CONTROLLER             PARAMETERS   AGE
nginx   k8s.io/ingress-nginx   <none>       29m

$ kubectl -n ingress-nginx get deploy,svc,pods
NAME                                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/ingress-nginx-controller   1/1     1            1           29m

NAME                                         TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                      AGE
service/ingress-nginx-controller             LoadBalancer   10.96.197.125   <pending>     80:31106/TCP,443:30235/TCP   29m
service/ingress-nginx-controller-admission   ClusterIP      10.96.48.93     <none>        443/TCP                      29m

NAME                                            READY   STATUS    RESTARTS   AGE
pod/ingress-nginx-controller-596f5b6bcf-7p6rm   1/1     Running   0          29m

$ kubectl -n ingress-nginx get deploy ingress-nginx-controller -o jsonpath='{...image}{...args}' | tr ',' '\n'
registry.k8s.io/ingress-nginx/controller:v1.15.1@sha256:594ceea7...
["/nginx-ingress-controller"
"--election-id=ingress-nginx-leader"
"--controller-class=k8s.io/ingress-nginx"
"--ingress-class=nginx"
...
"--watch-ingress-without-class=true"
"--publish-status-address=localhost"]
```

`--controller-class=k8s.io/ingress-nginx` matches the `CONTROLLER` of
IngressClass `nginx`. That is how the controller decides which Ingress objects
belong to it. (On kind the controller Pod also binds the node's ports 80/443
through `hostPort`, which is how host port 8080 reaches it.)

---

## The experiment: an Ingress with no controller vs the same Ingress with one

### 1. Ingress whose class no controller owns

```console
$ kubectl apply -f app.yaml                      # namespace, Deployment "hello", Service "hello"
$ kubectl apply -f ingress-no-controller.yaml    # ingressClassName: no-such-class
ingress.networking.k8s.io/demo created

$ kubectl -n s12-ingress get ingress demo        # 20 seconds later
NAME   CLASS           HOSTS            ADDRESS   PORTS   AGE
demo   no-such-class   demo.s12.local             80      20s

$ kubectl -n s12-ingress describe ingress demo
Ingress Class:    no-such-class
Rules:
  Host            Path  Backends
  ----            ----  --------
  demo.s12.local  
                  /   hello:80 (10.244.0.80:8080)
Events:           <none>
```

The object is valid and stored, and its backend even resolves to a Pod IP. But
the `ADDRESS` column is **empty** and there are **no events**: nothing has
picked it up. Traffic for the host goes nowhere useful:

```console
$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' -H 'Host: demo.s12.local' http://localhost:8080/
HTTP 404

$ curl -s -H 'Host: demo.s12.local' http://localhost:8080/ | grep -o '<title>.*</title>'
<title>404 Not Found</title>

$ kubectl -n ingress-nginx exec deploy/ingress-nginx-controller -- grep -c 'demo.s12.local' /etc/nginx/nginx.conf
0
```

The nginx controller is running, but it has **zero lines** for this host in its
config, so its default server answers 404. Its log says why:

```console
$ kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --since=60s | grep -i demo
W1007 13:37:17.412561      11 controller.go:352] ignoring ingress demo in s12-ingress based on annotation : no object matching key "no-such-class" in local store
I1007 13:37:17.418113      11 store.go:439] "Ignoring ingress because of error while validating ingress class" ingress="s12-ingress/demo" error="no object matching key \"no-such-class\" in local store"
```

### 2. The same Ingress, class `nginx`

Only one line changed: `ingressClassName: nginx`.

```console
$ kubectl apply -f ingress-nginx-class.yaml
ingress.networking.k8s.io/demo configured

$ kubectl -n s12-ingress get ingress demo
NAME   CLASS   HOSTS            ADDRESS     PORTS   AGE
demo   nginx   demo.s12.local   localhost   80      45s

$ kubectl -n s12-ingress describe ingress demo | sed -n '/^Events:/,$p'
Events:
  Type    Reason  Age               From                      Message
  ----    ------  ----              ----                      -------
  Normal  Sync    9s (x2 over 25s)  nginx-ingress-controller  Scheduled for sync
```

Now there is an `ADDRESS`, written by the controller (`--publish-status-address=localhost`),
and a `Sync` event from `nginx-ingress-controller`. The routing works:

```console
$ curl -s -w 'HTTP %{http_code}\n' -H 'Host: demo.s12.local' http://localhost:8080/
hello from the s12-ingress demo app
HTTP 200

$ curl -s -w 'HTTP %{http_code}\n' --resolve demo.s12.local:8080:127.0.0.1 http://demo.s12.local:8080/
hello from the s12-ingress demo app
HTTP 200

$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' -H 'Host: other.s12.local' http://localhost:8080/
HTTP 404
```

Here is what the controller did with the Ingress. Its log shows a reload:

```console
$ kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --since=60s | grep -iE 's12-ingress|demo.s12|reload'
I1007 13:37:37.779434  event.go:377] Event(...Kind:"Ingress", Namespace:"s12-ingress", Name:"demo"...): type: 'Normal' reason: 'Sync' Scheduled for sync
I1007 13:37:37.780930  controller.go:217] "Configuration changes detected, backend reload required"
I1007 13:37:37.807733  controller.go:231] "Backend successfully reloaded"
I1007 13:37:53.133416  status.go:311] "updating Ingress status" namespace="s12-ingress" ingress="demo" currentValue=null newValue=[{"hostname":"localhost"}]
192.168.65.1 - - [07/Oct/2026:13:38:03 +0000] "GET / HTTP/1.1" 200 36 "-" "curl/8.7.1" 77 0.006 [s12-ingress-hello-80] [] 10.244.0.80:8080 36 0.006 200 19e7...
```

…and the `server` block it generated in its own `nginx.conf`:

```console
$ kubectl -n ingress-nginx exec deploy/ingress-nginx-controller -- grep -n 'demo.s12.local' /etc/nginx/nginx.conf
335:	## start server demo.s12.local
337:		server_name "demo.s12.local" ;
448:	## end server demo.s12.local

$ kubectl -n ingress-nginx exec deploy/ingress-nginx-controller -- sed -n '/## start server demo.s12.local/,/location \/ {/p' /etc/nginx/nginx.conf
	## start server demo.s12.local
	server {
		server_name "demo.s12.local" ;
		listen 80  ;
		listen 443  ssl;
		...
		location "/" {
			set $namespace      "s12-ingress";
			set $ingress_name   "demo";
			set $service_name   "hello";
			set $service_port   "80";
			set $location_path  "/";
```

The 15-line Ingress became a ~110-line nginx `server` block (lines 335–448),
and the access log shows the request going straight to the **Pod IP**
`10.244.0.80:8080` (upstream `[s12-ingress-hello-80]`). The controller skips the
Service's ClusterIP and load-balances across the EndpointSlice itself.

---

## The difference

| | Ingress | Ingress Controller |
|---|---|---|
| **What it is** | An API object (YAML) stored in etcd | A running Deployment of proxy Pods |
| **Who writes it** | App teams, one per app or host | Platform team installs it once per cluster (Helm/manifest) |
| **Does it handle traffic?** | No | Yes: it is the reverse proxy that requests actually pass through |
| **Built into Kubernetes?** | Yes, `networking.k8s.io/v1` is a core API | **No**: nothing ships by default; you choose and install one |
| **Scope** | Routing rules for some hosts/paths in one namespace | Implements *all* Ingresses of its class, cluster-wide |
| **Linked by** | `spec.ingressClassName` | `IngressClass.spec.controller` = its `--controller-class` |
| **Without the other** | Object is stored but ignored: no ADDRESS, 404 (part 1 above) | Proxy runs but has no routes: default backend 404 for every host |

## Why both are required

Kubernetes separates **what you want** from **how it is done**, the same way a
Deployment (desired state) needs the controller-manager (the loop that acts on
it). The Ingress is the *what*. It is portable, and the same YAML works on any
cluster. The controller is the *how*: nginx here, an AWS ALB on EKS, a GCE load
balancer on GKE, Traefik on k3s. Without a controller the Ingress is only an
intention, as part 1 shows. Without Ingress objects the controller has no
routes, and every host gets the default 404. You need both to get a request
from the outside to a Pod.

## Examples

| Controller | Where you'd see it | Implements Ingress by |
|---|---|---|
| **ingress-nginx** (used here) | Any cluster; kind, bare metal | Generating `nginx.conf` and reloading |
| AWS Load Balancer Controller | EKS | Creating an **ALB** with listener rules per Ingress |
| GKE Ingress | GKE | Creating a Google Cloud HTTP(S) load balancer |
| Traefik | k3s default | Dynamic routing table, no reloads |
| HAProxy / Contour (Envoy) / Kong / Istio gateway | various | Their own proxy config |

Several controllers can run in the same cluster. Each one only implements
Ingresses whose `ingressClassName` points at its IngressClass. That is exactly
the mechanism part 1 used to make ingress-nginx ignore the object.

> Related: the [Gateway API](https://gateway-api.sigs.k8s.io/) is the newer
> successor with the same split: `GatewayClass`/`Gateway` (the controller
> side) and `HTTPRoute` (the app's rules).

Cleanup: `kubectl delete namespace s12-ingress`.
