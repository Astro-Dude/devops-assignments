#!/bin/bash
# usage: waitobj.sh present|absent  -- polls every 3s for configmap feature-flags
want=$1
k() { kubectl --context kind-hw-s20 "$@"; }
echo "TIME      APP-SYNC   SYNCED-REV  configmap/feature-flags"
while true; do
  s=$(k get app session20-gitops -n argocd -o jsonpath='{.status.sync.status} {.status.sync.revision}')
  if k get cm feature-flags -n gitops-demo >/dev/null 2>&1; then c=present; else c=absent; fi
  set -- $s
  printf "%s  %-9s  %-10s  %s\n" "$(date +%H:%M:%S)" "$1" "${2:0:7}" "$c"
  [[ $c == $want ]] && break
  sleep 3
done
