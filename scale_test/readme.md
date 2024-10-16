# Control Plane Scale Test

Control Plane scale testing via kube-burner utility. It creates `NUM_GWS` Gateways each having `NUM_LISTENERS` listeners configured. For each Gateway one policy of each Kind (AuthPolicy, DNSPolicy, RateLimitPolicy, TLSPolicy) is created. For each listener one AuthPolicy and one RateLimitPolicy is created.

## Prerequisites

This test assumes that Kuadrant together with all the dependencies (Gateway API, Istio, Certificate Manager etc) are installed. A ClusterIssuer (self-signed one is enough) is expected to exist too. Also make sure to port-forward Prometheus instance so that it is possible for kube-burner to query it.

The following environment variables will need to be set to run the tests:

```
export KUADRANT_AWS_SECRET_ACCESS_KEY=[key]
export KUADRANT_AWS_ACCESS_KEY_ID=[id]
export KUADRANT_ZONE_ROOT_DOMAIN=[domain]
export KUADRANT_AWS_REGION=[region]
export PROMETHEUS_URL=http://127.0.0.1:9090
export PROMETHEUS_TOKEN=""
export OS_INDEXING=true   # if sending metrics to opensearch/elasticsearch
export ES_SERVER=https://[user]:[password]@[host]:[port]

export NUM_GWS=1
export NUM_LISTENERS=1
```

If you want to disable indexing you need to explicitly set related environment variables to an empty string:
```
export OS_INDEXING= # to disable indexing
export ES_SERVER= # to disable indexing
```

## Execution

`kube-burner init -c ./config.yaml --timeout 5m --uuid scale-test-$(openssl rand -hex 3)`

Don't forget to increase the timeout if larger number of CRs are to be created.

## Setting up a local cluster for execution

Follow the instructions in the Prerequisites section.

Clone the [kuadrant-operator](https://github.com/Kuadrant/kuadrant-operator) repo:

```bash
CONTAINER_ENGINE=podman make local-setup
```

Deploy the observability stack, as per the instructions in https://github.com/Kuadrant/kuadrant-operator/blob/main/config/observability/README.md

Create the Kuadrant resource:

```bash
kubectl create -f ./config/samples/kuadrant_v1beta1_kuadrant.yaml -n kuadrant-system
```

Create a ClusterIssuer:

```bash
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
EOF
```

Port forward to Prometheus:

```bash
kubectl -n monitoring port-forward svc/prometheus-k8s 9090:9090
```

Run kube-burner (described in more detail above):

```bash
kube-burner init -c ./config.yaml --timeout 5m
```
