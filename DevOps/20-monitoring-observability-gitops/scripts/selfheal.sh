#!/bin/bash
k() { kubectl --context kind-hw-s20 "$@"; }
echo "# $(date +%H:%M:%S) state before drift:"
echo "\$ kubectl get deploy gitops-web -n gitops-demo"; k get deploy gitops-web -n gitops-demo
echo
echo "# $(date +%H:%M:%S) manual drift #1: scale out-of-band"
echo "\$ kubectl scale deploy gitops-web -n gitops-demo --replicas=1"; k scale deploy gitops-web -n gitops-demo --replicas=1
echo "# $(date +%H:%M:%S) manual drift #2: edit the live ConfigMap out-of-band"
echo "\$ kubectl patch cm gitops-web-content -n gitops-demo --type merge -p '{\"data\":{\"index.html\":\"hacked by hand\\n\"}}'"
k patch cm gitops-web-content -n gitops-demo --type merge -p '{"data":{"index.html":"hacked by hand\n"}}'
echo
echo "TIME      SPEC-REPLICAS  READY  APP-SYNC   CONFIGMAP index.html (first line)"
for i in $(seq 1 40); do
  r=$(k get deploy gitops-web -n gitops-demo -o jsonpath='{.spec.replicas} {.status.readyReplicas}')
  s=$(k get app session20-gitops -n argocd -o jsonpath='{.status.sync.status}')
  c=$(k get cm gitops-web-content -n gitops-demo -o jsonpath='{.data.index\.html}' | head -1)
  set -- $r
  printf "%s  %-13s  %-5s  %-9s  %s\n" "$(date +%H:%M:%S)" "$1" "${2:-0}" "$s" "$c"
  if [[ "$1" == 3 && "${2:-0}" == 3 && "$c" == "<html>"* && $i -gt 2 ]]; then break; fi
  sleep 1
done
echo
echo "\$ kubectl get application session20-gitops -n argocd -o jsonpath='{.status.operationState.operation.initiatedBy} {.status.operationState.phase} {.status.operationState.message}'"
k get application session20-gitops -n argocd -o jsonpath='{.status.operationState.operation.initiatedBy} {.status.operationState.phase} {.status.operationState.message}{"\n"}'
echo "\$ kubectl get application session20-gitops -n argocd -o jsonpath='{range .status.operationState.syncResult.resources[*]}{.kind}/{.name}: {.status} {.message}{\"\\n\"}{end}'"
k get application session20-gitops -n argocd -o jsonpath='{range .status.operationState.syncResult.resources[*]}{.kind}/{.name}: {.status} {.message}{"\n"}{end}'
echo "\$ kubectl get events -n gitops-demo --sort-by=.lastTimestamp | tail -8"
k get events -n gitops-demo --sort-by=.lastTimestamp | tail -8
