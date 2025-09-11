#!/bin/bash
set -exuo pipefail

UUID="$1"

for gw in 1 2; do
  for listener in {1..64}; do
    url="http://gw${gw}-api${listener}.${UUID}.${KUADRANT_ZONE_ROOT_DOMAIN}/get"
    if ! curl -sf -o /dev/null "$url"; then
      echo "Failed: $url" >&2
      exit 1
    fi
  done
done
echo "All URLs work as expected"
