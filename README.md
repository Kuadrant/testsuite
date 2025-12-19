# Kuadrant E2E testsuite

This repository contains end-to-end (E2E) tests for the [Kuadrant](https://kuadrant.io/) project, intended for contributors and maintainers to validate Kuadrant behavior in both single- and multi-cluster environments.

**What’s tested:**
* **Core policies**: AuthPolicy, RateLimitPolicy, TokenRateLimitPolicy, DNSPolicy, TLSPolicy
* **Policy extensions**: OIDCPolicy, PlanPolicy, TelemetryPolicy
* **Policy behavior**: defaults, overrides, reconciliation
* **Observability**: metrics and tracing
* **Multi-cluster**: load balancing, global rate limiting, CoreDNS delegation
* **UI**: Console Plugin

## Prerequisites

### Local Development
* [Python 3.11+](https://www.python.org/downloads/) and [Poetry](https://python-poetry.org/docs/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/) or [oc](https://docs.redhat.com/en/documentation/openshift_container_platform/4.11/html/cli_tools/openshift-cli-oc) (OpenShift CLI)
* [CFSSL](https://github.com/cloudflare/cfssl)
* [git](https://git-scm.com/downloads)
* Access to one or more Kubernetes clusters with Kuadrant already deployed

Once all prerequisites are installed, install dependencies and create a Python virtual environment by running:
```shell
make poetry
```

### Container-based Testing
* Container runtime ([podman](https://podman.io/docs/installation) or [docker](https://www.docker.com/get-started/))
* Access to one or more Kubernetes clusters with Kuadrant already deployed

> **For Kuadrant installation instructions, see:**
> - [Kuadrant Helm Charts](https://github.com/Kuadrant/helm-charts) for any Kubernetes cluster
> - [Deploying Kuadrant via OLM](https://github.com/Kuadrant/helm-charts-olm/blob/main/README.md) for OpenShift (recommended as it also deploys testing tools)

## Configuration

The Kuadrant testsuite uses [Dynaconf](https://www.dynaconf.com/) for configuration.

### Settings Files
For local development, create a YAML configuration file at `config/settings.local.yaml`.
See [config/settings.local.yaml.tpl](https://github.com/Kuadrant/testsuite/blob/main/config/settings.local.yaml.tpl) for all available configuration options.

### Environment Variables
Settings can also be configured using environment variables. All variables use the `KUADRANT` prefix, for example:

```bash
export KUADRANT_KEYCLOAK__url="https://my-sso.net"
```

For more details, see the [Dynaconf wiki page](https://www.dynaconf.com/envvars/).

### Kubernetes Auto-Fetching
Some configuration options can be fetched from Kubernetes. To install helper services (e.g., Keycloak, Jaeger, MockServer, Redis), see [Testing charts](https://github.com/Kuadrant/helm-charts-olm?tab=readme-ov-file#testing-charts):

```bash
# Install tools operators
helm install --values values-tools.yaml --wait -g charts/tools-operators
# Install tools instances
helm install --values values-tools.yaml --wait --timeout 10m -g charts/tools-instances
```

## Test Requirements

### Single-cluster tests

| Test Type                | Requirements                                                                                                                    | Make Target                    |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------|--------------------------------|
| **Kuadrant**             | <ul><li>Kuadrant deployment*</li><li>Gateway API*</li><li>cert-manager</li><li>DNS Secret*</li><li>TLS ClusterIssuer*</li></ul> | `make test` or `make kuadrant` |
| **Authorino standalone** | <ul><li>Authorino Operator</li></ul>                                                                                            | `make authorino-standalone`    |
| **DNS & TLS Policies**   | <ul><li>Kuadrant deployment*</li><li>Gateway API*</li><li>DNS Secret*</li><li>cert-manager</li><li>TLS ClusterIssuer*</li></ul> | `make dnstls`                  |
| **Console Plugin**       | <ul><li>OpenShift</li><li>Kuadrant Console Plugin enabled</li><li>HTPasswd authentication</li></ul>                             | `make ui`                      |

> **Important Notes:**
> * **Kuadrant deployment*** represents multiple operators: Kuadrant Operator, Authorino Operator, Limitador, and DNS Operator.
> * **Gateway API*** requires an implementation (e.g., Istio, Envoy Gateway). On OpenShift, this is typically provided by Service Mesh.
> * **DNS Secret*** needs `base_domain` annotation and type `kuadrant.io/aws|gcp|azure` (see example below).
> * **TLS ClusterIssuer*** can be a self-signed CA from [helm-charts-olm](https://github.com/Kuadrant/helm-charts-olm/tree/4ffbb308f798a790445f1e30ff18a4cc2496fa30/charts/kuadrant-instances/templates/cert-manager) or Let's Encrypt (`letsencrypt-staging-issuer`).
> * **Keycloak** can be auto-fetched if deployed via [helm](https://github.com/Kuadrant/helm-charts-olm?tab=readme-ov-file#testing-charts) or configured manually. Required for most AuthPolicy tests.

<details>
<summary><b>DNS Provider Secret example (click to expand)</b></summary>

```yaml
kind: Secret
apiVersion: v1
metadata:
  name: aws-credentials
  namespace: kuadrant
  annotations:
    base_domain: example.com
data:
  AWS_ACCESS_KEY_ID: <key>
  AWS_REGION: <region>
  AWS_SECRET_ACCESS_KEY: <key>
type: kuadrant.io/aws
```
</details>

### Multi-cluster tests

**Base requirements:** 2+ clusters (`cluster2` required, `cluster3` optional), matching namespaces on all clusters, and DNS Secret + TLS ClusterIssuer on all clusters.

| Test Type                | Additional Requirements                                                                                                                                                                     | Make Target                                                |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| **Load balancing**       | DNS servers with geo-codes                                                                                                                                                                  | `make multicluster`                                        |
| **CoreDNS delegation**   | CoreDNS zone + [CoreDNS tools](https://github.com/Kuadrant/helm-charts-olm/tree/4ffbb308f798a790445f1e30ff18a4cc2496fa30/charts/tools-instances/templates/coredns) deployed on all clusters | `make coredns_one_primary` or `make coredns_two_primaries` |
| **Global rate limiting** | Shared storage (Redis/Dragonfly/Valkey)                                                                                                                                                     | `make multicluster`                                        |

## Running the Tests

### Locally

For development and debugging, running the tests locally is recommended.

Test commands:

```shell
make smoke          # Quick smoke test to verify environment setup
make test           # Run the full test suite
make <test-path>    # Run a specific test file or directory
# or
poetry run pytest -v <test-path>
```

Run `make help` to list all available targets. Most `make` targets run in parallel by default.

You can also pass pytest flags to `make` targets using the `flags` environment variable. **Note:** The `flags` variable must be placed **before** the `make` command (see [pytest command-line flags](https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags) for more options):

```shell
flags=--lf make test      # Run last failed tests
flags=-n1 make test       # Run tests with just one thread
flags=-v make test        # Run in verbose mode
flags="-v --lf" make test # Multiple flags (use quotes)
```

### From a Container

To simply run tests, using the container image is the easiest option. Run it with your kubeconfig mounted (it must be readable by the container). If you omit any variables (for example, Auth0 credentials), the corresponding tests will be skipped. Mount a local directory to `/test-run-results` to persist test results.

**E2E tests** - `quay.io/kuadrant/testsuite:latest`

With tools setup:
```bash
podman run \
  -v $HOME/.kube/config:/run/kubeconfig:z \
  -v $(pwd)/test-run-results:/test-run-results:z \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT=authorino \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT2=authorino2 \
  -e KUADRANT_AUTH0__url="AUTH0_URL" \
  -e KUADRANT_AUTH0__client_id="AUTH0_CLIENT_ID" \
  -e KUADRANT_AUTH0__client_secret="AUTH0_CLIENT_SECRET" \
  quay.io/kuadrant/testsuite:latest
```

Without tools (manual Keycloak config):
```bash
podman run \
  -v $HOME/.kube/config:/run/kubeconfig:z \
  -v $(pwd)/test-run-results:/test-run-results:z \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT=authorino \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT2=authorino2 \
  -e KUADRANT_KEYCLOAK__url="https://my-sso.net" \
  -e KUADRANT_KEYCLOAK__password="ADMIN_PASSWORD" \
  -e KUADRANT_KEYCLOAK__username="ADMIN_USERNAME" \
  -e KUADRANT_AUTH0__url="AUTH0_URL" \
  -e KUADRANT_AUTH0__client_id="AUTH0_CLIENT_ID" \
  -e KUADRANT_AUTH0__client_secret="AUTH0_CLIENT_SECRET" \
  quay.io/kuadrant/testsuite:latest
```

**UI tests** - `quay.io/kuadrant/testsuite-ui:unstable`

The UI container expects a settings file to be mounted, containing the console username and password used to authenticate against the OpenShift console.

```bash
podman run --rm \
  -v $HOME/.kube/config:/run/kubeconfig:z \
  -v $(pwd)/test-run-results:/test-run-results:z \
  -v $(pwd)/settings.local.yaml:/run/secrets.yaml:Z \
  quay.io/kuadrant/testsuite-ui:unstable
```

## Developing Authorino Tests

When developing Authorino tests, you may need to inspect the full authorization JSON returned by Authorino.

<details>
<summary>AuthConfig example for returning full authorization context</summary>

```yaml
apiVersion: authorino.kuadrant.io/v1beta3
kind: AuthConfig
metadata:
  name: example
spec:
  hosts:
    - '*'
  response:
    success:
      headers:
        auth-json:
          json:
            properties:
              auth:
                selector: auth
              context:
                selector: context
```

</details>

Another useful tool is the [OPA Playground](https://play.openpolicyagent.org/) for developing and validating OPA policies.

## Contributing

See the [Kuadrant Testsuite Contribution Guide](https://github.com/Kuadrant/testsuite/blob/main/CONTRIBUTING.md) for information on how to contribute to the Kuadrant testsuite.
