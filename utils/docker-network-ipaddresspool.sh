#!/bin/bash

# Generates a MetalLB IpAddressPool for the given docker network.
# https://metallb.org/configuration/#defining-the-ips-to-assign-to-the-load-balancer-services
#
# Example:
# ./utils/docker-network-ipaddresspool.sh kind | kubectl apply -n metallb-system -f -

set -euo pipefail

networkName=$1
CONTAINER_ENGINE="${CONTAINER_ENGINE:-docker}"

SUBNET=""
set +e
if [[ "$CONTAINER_ENGINE" == "podman" ]]; then
  SUBNET=$(podman network inspect -f '{{range .Subnets}}{{if eq (len .Subnet.IP) 4}}{{.Subnet}}{{end}}{{end}}' $networkName)
else
  SUBNET=$(docker network inspect $networkName --format '{{json .IPAM.Config}}' | yq '.[] | select( .Subnet | test("^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}/\d+$")) | .Subnet')
fi
set -e

if [[ -z "$SUBNET" ]]; then
  echo "Error: parsing IPv4 network address for '$networkName' docker network"
  exit 1
fi

network=$(echo $SUBNET | cut -d/ -f1)
# shellcheck disable=SC2206
octets=(${network//./ })

address="${octets[0]}.${octets[1]}.${octets[2]}.0/28"

echo "IPAddressPool address: '$address' (subnet: '$SUBNET')" >&2

cat <<EOF | ADDRESS=$address yq '(select(.kind == "IPAddressPool") | .spec.addresses[0]) = env(ADDRESS)'
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: kuadrant-local
spec:
  addresses: []
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: empty
EOF
