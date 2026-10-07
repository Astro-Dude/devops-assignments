#!/bin/bash
# prints the command (kubectl/helm shown without the --context flag) and runs it against kind-hw-s20
echo "\$ $*"
kubectl() { command kubectl --context kind-hw-s20 "$@"; }
helm() { command helm --kube-context kind-hw-s20 "$@"; }
export -f kubectl helm
bash -c "$*" 2>&1
echo
