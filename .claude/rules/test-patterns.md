---
paths:
  - "testsuite/tests/**/*.py"
---

# Test Patterns and Fixtures

## Conftest Hierarchy and Fixture Inheritance

The testsuite uses a layered conftest hierarchy where each level provides fixtures that lower levels can override:

1. **Root conftest** (`testsuite/tests/conftest.py`): Session-level infrastructure - `testconfig`, `cluster`, `exposer`, `blame`, `label`, `wildcard_domain`, `keycloak`, `prometheus`, `cluster_issuer`, `dns_provider_secret`
2. **Singlecluster conftest** (`testsuite/tests/singlecluster/conftest.py`): Module-level defaults - `backend`, `gateway`, `route`, `hostname`, `client`, `authorization`, `rate_limit`, `commit`
3. **Test-specific conftest**: Overrides/extends fixtures for specific test scenarios

Tests customize behavior by overriding fixtures in their local `conftest.py`. For example, a TLS test overrides `gateway` to use `TLSGatewayListener` instead of the default `GatewayListener`.

## Commit Fixture Pattern

The `commit` fixture is the central mechanism for creating and cleaning up Kuadrant policies. It is typically `autouse=True` and `scope="module"`.

**Important distinction**: The `commit` fixture commits only Kuadrant policies (AuthPolicy, RateLimitPolicy, DNSPolicy, TLSPolicy) and Kuadrant-related CRDs. Other Kubernetes objects (backends, gateways, routes, secrets) are committed from within their own respective fixtures.

```python
# Policies are committed in the commit fixture
@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Commits all policies before tests"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()

# But backends, routes, gateways commit themselves in their fixtures
@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(cluster, blame("httpbin"), label, testconfig["httpbin"]["image"])
    request.addfinalizer(httpbin.delete)
    httpbin.commit()  # Committed here, not in the commit fixture
    return httpbin
```

When extending the commit fixture for additional policies (e.g., DNSPolicy, TLSPolicy), add them to the loop:

```python
@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all policies before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()
```

## Fixture Factory Pattern

For creating multiple instances of a resource within a test module:

```python
@pytest.fixture(scope="module")
def create_api_key(blame, request, cluster):
    """Factory for creating API key Secrets"""

    def _create_secret(name, label_selector, api_key, ocp=cluster, annotations=None):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key, annotations)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret

# Usage:
@pytest.fixture(scope="module")
def api_key(create_api_key, user_label):
    """Create API key for test user"""
    return create_api_key("api-key", user_label, "test-key-value")
```

## Indirect Parametrization (Route vs Gateway Targeting)

A common pattern for testing policies at both route and gateway level:

```python
@pytest.fixture(scope="module")
def rate_limit(kuadrant, cluster, blame, request, module_label, route, gateway):
    """Rate limit policy with configurable target (route or gateway)"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))
    return RateLimitPolicy.create_instance(cluster, blame("limit"), target_ref, labels={"testRun": module_label})

# Usage in test:
@pytest.mark.parametrize("rate_limit", ["route", "gateway"], indirect=True)
def test_limit(client, rate_limit):
    """Test rate limit on both route and gateway targets"""
    ...
```

## HTTP Client and Batch Requests

### KuadrantClient

The `KuadrantClient` (`testsuite/httpx/__init__.py`) wraps httpx with automatic retry logic using exponential backoff. It retries on DNS errors, 503 responses, server disconnections, timeouts, and TLS errors.

### `get_many()` and `assert_all()`

For rate limiting tests that need to send multiple requests and verify responses:

```python
def test_rate_limit(client):
    """Test that rate limit is enforced after 5 requests"""
    # Send 5 requests - all should succeed
    responses = client.get_many("/get", count=5)
    responses.assert_all(200)

    # 6th request should be rate limited
    response = client.get("/get")
    assert response.status_code == 429
```

`get_many(url, count)` returns a `ResultList`, which is a list with an `assert_all(status_code)` method that asserts every response has the expected status code, with detailed error messages on failure.

## Metrics Testing Pattern

Metrics tests follow a specific pattern to minimize Prometheus API calls. Fetch metrics once, then filter multiple times using `has_label()`:

```python
from testsuite.prometheus import has_label

@pytest.fixture(scope="module")
def dns_metrics(prometheus, service_monitor):
    """Fetch all DNS operator metrics once"""
    prometheus.wait_for_scrape(service_monitor, "/metrics")
    return prometheus.get_metrics(
        labels={"service": "dns-operator-controller-manager-metrics-service"}
    )

def test_record_ready(dns_metrics, dnsrecord):
    """Test that dns_provider_record_ready metric exists with correct labels"""
    # Filter the pre-fetched metrics - no additional Prometheus calls
    record_metrics = dns_metrics.filter(
        has_label("dns_record_name", dnsrecord.model.status.zoneID)
    )
    ready_metric = record_metrics.filter(
        has_label("__name__", "dns_provider_record_ready")
        and has_label("dns_record_is_delegating", "false")
    )
    assert len(ready_metric.metrics) == 1
    assert ready_metric.values[0] == 1.0

def test_write_counter_exists(dns_metrics, dnsrecord):
    """Test that write counter metric is present"""
    record_metrics = dns_metrics.filter(
        has_label("dns_record_name", dnsrecord.model.status.zoneID)
    )
    assert "dns_provider_write_counter" in record_metrics.names
```

**Key `Metrics` properties:**
- `.filter(predicate)` - Returns new `Metrics` with only matching entries
- `.names` - List of metric names (`__name__` label values)
- `.values` - List of metric values
- `.metrics` - Raw metric dicts with all labels

## Additional Pytest Patterns

### Pytest Parametrize with IDs

```python
@pytest.fixture(
    scope="module",
    params=[
        pytest.param(Limit(2, "15s"), id="2 requests every 15 sec", marks=[pytest.mark.smoke]),
        pytest.param(Limit(5, "10s"), id="5 requests every 10 sec"),
    ],
)
def limit(request):
    """Combination of max requests and time period"""
    return request.param
```

### Issue Tracking with xfail

```python
@pytest.mark.issue("https://github.com/Kuadrant/limitador-operator/issues/197")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/limitador-operator/issues/197")
def test_known_issue(client):
    """Test for a known bug - expected to fail until fixed"""
    ...
```

### Module-level pytestmark

Apply markers to all tests in a module:

```python
pytestmark = [pytest.mark.authorino, pytest.mark.smoke]
```

### skip_or_fail Pattern

Tests can either skip or fail based on missing capabilities, controlled by the `--enforce` flag passed to pytest:

```python
@pytest.fixture(scope="session")
def skip_or_fail(request):
    """Skips or fails tests depending on --enforce option"""
    return pytest.fail if request.config.getoption("--enforce") else pytest.skip
```

### Result Error Checking

The `Result` object provides methods for checking specific error types:

```python
def test_tls_enforcement(client):
    """Test that TLS is required"""
    response = client.get("/get")
    assert response.has_tls_error() or response.has_cert_verify_error()
```