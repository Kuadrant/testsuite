# Control Plane Scale Test

Control Plane scale testing via kube-burner utility

## Prerequisities

This test assumes that Kuadrant together with all the dependencies (Gateway API, Istio, Certificate Manager etc) is installed. A ClusterIssuer (self-signed one is enough) is expected to exist too. Also make sure to port-forward Prometheus instance so that it is possible for kube-burner to query it.

Provide the AWS credentials for DNS setup in `aws-credentials.yaml`
Replace the `the.domain.iown` placeholder with the actual domain in `gw.yaml` and `httproute.yaml`.

Create an empty `./metrics` directory where the data returned from Prometheus are to be stored.

## Execution

`kube-burner init -c ./config.yaml --timeout 5m`
