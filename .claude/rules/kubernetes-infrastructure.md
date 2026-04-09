---
paths:
  - "testsuite/kubernetes/**/*.py"
  - "testsuite/gateway/**/*.py"
  - "testsuite/backend/**/*.py"
  - "testsuite/tests/**/*.py"
---

# Kubernetes Infrastructure

## KubernetesObject Interface

All Kubernetes objects in the testsuite inherit from `KubernetesObject` (`testsuite/kubernetes/__init__.py`). When creating a new Kubernetes object type, follow this interface:

```python
from testsuite.kubernetes import KubernetesObject

class MyResource(KubernetesObject):
    """Custom Kubernetes resource"""

    @classmethod
    def create_instance(cls, cluster, name, ...):
        """Creates new instance of MyResource"""
        model = {
            "apiVersion": "example.io/v1",
            "kind": "MyResource",
            "metadata": {"name": name, "namespace": cluster.project},
            "spec": { ... },
        }
        return cls(model, context=cluster.context)
```

**Key methods:**
- `create_instance(cluster, name, ...)` - Class method that builds the model dict and returns an instance
- `commit()` - Creates the object on the Kubernetes server, sets `_committed = True`
- `delete(ignore_not_found=True)` - Deletes the resource from the server
- `wait_until(test_function, timelimit=60)` - Polls until condition is met
- `apply(modifier_func)` - Modifies and applies changes to an already committed object

**The `@modify` decorator** (`testsuite/kubernetes/__init__.py`): Wraps methods that modify the object. If the object is already committed, it uses `modify_and_apply` to update it on the server. If not committed, it modifies the model directly. All mutating methods should use this decorator.

**`CustomResource`** extends `KubernetesObject` with `wait_for_ready()` which waits until all status conditions report `True`.

## Gateway and Listener Configuration

### HTTP Gateway (Default)

The default singlecluster gateway uses a plain HTTP `GatewayListener`:

```python
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway

@pytest.fixture(scope="session")
def gateway(request, cluster, blame, label, wildcard_domain):
    """Deploys Gateway with HTTP listener"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw
```

### TLS Gateway (Required for TLSPolicy)

**When using TLSPolicy in tests, the gateway MUST use `TLSGatewayListener` instead of `GatewayListener`.** The TLS listener configures HTTPS protocol, port 443, and references TLS certificate secrets:

```python
from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway

@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Returns ready gateway with TLS listener"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw
```

The `TLSGatewayListener` automatically configures TLS certificate references in the format `{gateway_name}-{listener_name}-tls`. TLSPolicy will provision these certificates via cert-manager.

### TLSPolicy and DNSPolicy Test Setup

Tests using TLSPolicy typically also usually require DNSPolicy and a `DNSPolicyExposer`:

```python
@pytest.fixture(scope="module")
def exposer(request, cluster):
    """DNSPolicyExposer for DNS/TLS tests"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer

@pytest.fixture(scope="module")
def tls_policy(blame, gateway, module_label, cluster_issuer):
    """TLSPolicy fixture"""
    return TLSPolicy.create_instance(
        gateway.cluster, blame("tls"), parent=gateway,
        issuer=cluster_issuer, labels={"app": module_label},
    )

@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label, dns_provider_secret):
    """DNSPolicy fixture"""
    return DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway,
        dns_provider_secret, labels={"app": module_label},
    )
```

## Exposers

Exposers make hostnames accessible from outside the cluster. The exposer type is determined by the `default_exposer` setting, but tests can override it. All exposers implement the `Exposer` base class (`testsuite/gateway/__init__.py`).

### Available Exposers

| Exposer                      | When to Use | Base Domain                                | How It Works |
|------------------------------|-------------|--------------------------------------------|--------------|
| `OpenShiftExposer` (default) | OpenShift clusters | `cluster.apps_url`                         | Creates OpenShift Route objects (edge or passthrough TLS termination) |
| `LoadBalancerServiceExposer` | Kind/local clusters | `"test.com"`                               | Uses Gateway's LoadBalancer external IP with `Host` header and SNI |
| `DNSPolicyExposer`           | DNS/TLS policy tests | Random subdomain of provider's base domain | Relies on DNSPolicy for actual exposure; reads base domain from provider secret annotation |
| `CoreDNSExposer`             | CoreDNS multicluster tests | Subdomain from `dns.coredns_zone` setting  | Extends `DNSPolicyExposer` with CoreDNS-specific zone |

### Exposer Override Example

```python
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer

@pytest.fixture(scope="module")
def exposer(request, cluster):
    """Override default exposer for DNS/TLS tests"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer
```

## Backend Options

The testsuite provides three backend types, all inheriting from `Backend` (`testsuite/backend/__init__.py`). Backends deploy a Deployment and Service in the test namespace.

### Httpbin (Default)

Standard HTTP echo backend. Used by most tests.

```python
from testsuite.backend.httpbin import Httpbin

@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(cluster, blame("httpbin"), label, testconfig["httpbin"]["image"])
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin
```

### MockserverBackend

Self-deployed Mockserver for mocking external HTTP endpoints. Uses a LoadBalancer service and configurable expectations via lifecycle hooks.

```python
from testsuite.backend.mockserver import MockserverBackend

@pytest.fixture(scope="module")
def mockserver_backend(request, cluster, blame, module_label, testconfig):
    """Deploys Mockserver backend"""
    backend = MockserverBackend(cluster, blame("mockserver"), module_label, testconfig["mockserver"]["image"])
    request.addfinalizer(backend.delete)
    backend.commit()
    return backend
```

### LlmSim

LLM inference simulator for testing token-based rate limiting. Mimics LLM API behavior.

```python
from testsuite.backend.llm_sim import LlmSim

@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys LLM simulator backend"""
    llm = LlmSim(cluster, blame("llm"), "test-model", label, testconfig["llm_sim"]["image"])
    request.addfinalizer(llm.delete)
    llm.commit()
    return llm
```

## RouteMatch Composition

For matching specific HTTP requests to backends:

```python
from testsuite.gateway import RouteMatch, PathMatch, HeadersMatch, MatchType, HTTPMethod

@pytest.fixture(scope="module")
def route(request, gateway, blame, hostname, backend, module_label):
    """Route with path prefix and header matching"""
    route = HTTPRoute.create_instance(gateway.cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_rule(
        backend,
        RouteMatch(
            path=PathMatch(type=MatchType.PATH_PREFIX, value="/api"),
            headers=[HeadersMatch(name="x-api-version", value="v2")],
            method=HTTPMethod.GET,
        ),
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route
```