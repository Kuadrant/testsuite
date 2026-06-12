"""
Tests for distributed tracing with only a RateLimitPolicy configured (no AuthPolicy).

With Gateway API-managed Istio, gateway traces are not available because the Istio CR cannot be
modified to enable tracing (meshConfig.enableTracing, extensionProviders) and the Telemetry
resource cannot be created. Gateway service assertions are conditional on has_ossm.
"""

import os

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.observability, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Configures basic rate limit policy."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()


@pytest.fixture(scope="module")
def trace_429(client, tracing, has_ossm):
    """
    Sends requests to exhaust the rate limit, produces a 429 response,
    and fetches the full wasm-shim trace.
    """
    responses = client.get_many("/get", 3)
    responses.assert_all(200)

    response_429 = client.get("/get", headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"})
    assert response_429.status_code == 429

    request_id = response_429.headers.get("x-request-id")
    min_procs = 3 if has_ossm else 2
    traces = tracing.get_traces(service="wasm-shim", min_processes=min_procs, tags={"request_id": request_id})
    assert len(traces) == 1, f"No trace was found in tracing backend with request_id: {request_id}"
    return traces[0]


def test_relevant_services_rate_limit_only(trace_429, label, has_ossm):
    """
    Test that traces with only a RateLimitPolicy include relevant Kuadrant services.
    Gateway service is only present with full OSSM3 Istio installation.
    Trace should not contain authorino since no authorization is involved.
    """

    process_services = trace_429.get_process_services()
    services = ["wasm-shim", "limitador"]
    if has_ossm:
        services.append(f"{label}.kuadrant")
    for service in services:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"

    assert (
        "authorino" not in process_services
    ), f"'authorino' should not be in trace with only RateLimitPolicy: {process_services}"
