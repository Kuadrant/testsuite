# Kuadrant E2E testsuite

This repository contains end-to-end tests for the [Kuadrant](https://kuadrant.io/) project, intended for
contributors and maintainers to validate Kuadrant behavior across single- and
multi-cluster environments.

**What's tested:**
* AuthPolicy
* RateLimitPolicy
* TokenRateLimitPolicy
* DNSPolicy
* TLSPolicy
* Policy extensions (OIDCPolicy, PlanPolicy, TelemetryPolicy)
* Policy behavior (defaults, overrides, reconciliation)
* Observability (metrics, tracing)
* Multi-cluster (load balancing, global rate limiting, CoreDNS delegation)
* Console Plugin

## Prerequisites

### Local Development
* [Python 3.11+](https://www.python.org/downloads/) and [Poetry](https://python-poetry.org/docs/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/) or [oc](https://docs.redhat.com/en/documentation/openshift_container_platform/4.11/html/cli_tools/openshift-cli-oc) (OpenShift CLI)
* [CFSSL](https://github.com/cloudflare/cfssl)
* [git](https://git-scm.com/downloads)
* Access to one or more Kubernetes clusters with Kuadrant deployed

Once all prerequisites are installed, run:
```shell
make poetry  # Install dependencies and create virtual environment
```

### Container-based Testing
* Container runtime ([podman](https://podman.io/docs/installation) or [docker](https://www.docker.com/get-started/))
* Access to one or more Kubernetes clusters with Kuadrant deployed

> **Note:** For instructions on setting up Kuadrant and the required tools on a cluster, see [Deploying Kuadrant via OLM](https://github.com/Kuadrant/helm-charts-olm/blob/main/README.md).

## Configuration

The Kuadrant testsuite uses [Dynaconf](https://www.dynaconf.com/) for configuration.

### Settings Files
For local development, create a YAML configuration file: **`config/settings.local.yaml`**.
See [config/settings.local.yaml.tpl](https://github.com/Kuadrant/testsuite/blob/main/config/settings.local.yaml.tpl) for all available configuration options.

### Environment Variables
Settings can also be configured using environment variables. All variables use the `KUADRANT` prefix, for example:

```bash
export KUADRANT_RHSSO__url="https://my-sso.net"
```

For more details, see the [Dynaconf wiki page](https://www.dynaconf.com/envvars/).

### Kubernetes Auto-Fetching
Some configuration options can be auto-discovered from Kubernetes. Use the [tools project](https://github.com/3scale-qe/tools) to easily deploy helper services (e.g., Keycloak, Jaeger, MockServer):

```bash
oc apply -k overlays/kuadrant/ --namespace tools
```

## Test Requirements

### Single-cluster tests

| Test Type                | Requirements                                                                    | Make Target                    |
|--------------------------|---------------------------------------------------------------------------------|--------------------------------|
| **Kuadrant**             | Kuadrant Operator + Gateway API + cert-manager + DNS Secret + TLS ClusterIssuer | `make test` or `make kuadrant` |
| **Authorino standalone** | Authorino Operator                                                              | `make authorino-standalone`    |
| **DNSPolicy**            | Kuadrant Operator + Gateway API + DNS Secret                                    | `make dnstls`                  |
| **TLSPolicy**            | Kuadrant Operator + Gateway API + cert-manager + TLS ClusterIssuer              | `make dnstls`                  |
| **Console Plugin**       | OpenShift + Kuadrant Console Plugin enabled + HTPasswd auth                     | `make ui`                      |

> **Note:**
> * **Keycloak** is required for most test targets (AuthPolicy testing). Deploy via [tools project](https://github.com/3scale-qe/tools) or configure manually via settings file or environment variables.
> * **Auth0** is optional and only needed for Auth0-specific tests.
> * **DNS Secret** requires `base_domain` annotation and type `kuadrant.io/aws|gcp|azure`.
> * **TLS ClusterIssuer** can be the self-signed CA ClusterIssuer from [helm-charts-olm](https://github.com/Kuadrant/helm-charts-olm/tree/4ffbb308f798a790445f1e30ff18a4cc2496fa30/charts/kuadrant-instances/templates/cert-manager) or an existing Let's Encrypt issuer named `letsencrypt-staging-issuer`.
> * **UI tests** use `console.username`/`console.password` or `KUBE_USER`/`KUBE_PASSWORD` env vars.

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

**Base requirements:** 2+ clusters (`cluster2` required, `cluster3` optional), matching namespaces on all clusters, DNS Secret + TLS ClusterIssuer on all clusters.

| Test Type                | Additional Requirements                                                                                                                                                                     | Make Target                                                |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| **Load balancing**       | DNS servers with geo-codes                                                                                                                                                                  | `make multicluster`                                        |
| **CoreDNS delegation**   | CoreDNS zone + [CoreDNS tools](https://github.com/Kuadrant/helm-charts-olm/tree/4ffbb308f798a790445f1e30ff18a4cc2496fa30/charts/tools-instances/templates/coredns) deployed on all clusters | `make coredns_one_primary` or `make coredns_two_primaries` |
| **Global rate limiting** | Shared storage (Redis/Dragonfly/Valkey)                                                                                                                                                     | `make multicluster`                                        |

> **Namespaces:**
> The default namespaces are `kuadrant` for resources and `kuadrant-system` for operators.
> If your installation uses different namespaces, update your configuration accordingly.

## Running the Tests

### Locally

For development and debugging, running the tests locally is recommended.

Once everything is set up and configured, start by running a quick smoke test to verify your environment and cluster configuration:

```shell
make smoke
```

You can run the full testsuite with:

```shell
make test
```

Or run specific tests with:

```shell
make <test-path>
# or
poetry run pytest -v <test-path>
```

You can also run tests in parallel:

```shell
poetry run pytest -n4
```

> **Note:** Most `make` targets already run tests in parallel by default (`-n4` or `-n2`).

See [Makefile](https://github.com/Kuadrant/testsuite/blob/main/Makefile) for other available `make` targets.

### From a Container

For just running tests without local setup, use the container image. Ensure you're logged into your cluster(s) first, then run the container with your kubeconfig mounted.

> **Note:** Ensure your kubeconfig has appropriate read permissions for the container to access it.

Environment variables are optional, and omitting a variable (e.g., Auth0 credentials) will skip related tests. Test results are saved to `/test-run-results` in the container (mount a local directory to persist them).

**Integration tests** - `quay.io/kuadrant/testsuite:latest`

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

**UI tests** - `quay.io/kuadrant/testsuite-ui:latest`

```bash
podman run --rm \
  -v $HOME/.kube/config:/run/kubeconfig:z \
  -v $(pwd)/test-run-results:/test-run-results:z \
  -v $(pwd)/settings.local.yaml:/run/secrets.yaml:Z \
  quay.io/kuadrant/testsuite-ui:latest
```

## Developing Tests

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
