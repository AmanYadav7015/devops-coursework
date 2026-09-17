#!/bin/sh
SVC="$1"
SECS="$2"
END=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt "$END" ]; do
  R=$(kubectl get endpointslices -n hw10 -l kubernetes.io/service-name="$SVC" \
        -o jsonpath='{.items[*].endpoints[*].conditions.ready}' 2>/dev/null \
        | tr ' ' '\n' | grep -c true)
  printf '%s  ready_endpoints=%s\n' "$(date +%H:%M:%S)" "$R"
done
