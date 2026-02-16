"""
Tests for distributed tracing with only a RateLimitPolicy configured (no AuthPolicy).
"""

import os
import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.observability, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Configures basic rate limit policy."""
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()


@pytest.fixture(scope="module")
def trace(client):
    """
    Sends requests to exhaust the rate limit and produce a 429 response.

    Returns the request_id of the 429 response for trace lookups.
    The 429 request includes a traceparent header to link gateway/istio traces
    with wasm-shim traces in a single distributed trace.
    """
    responses = client.get_many("/get", 3)
    responses.assert_all(200)

    response_429 = client.get("/get", headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"})
    assert response_429.status_code == 429

    return response_429.headers.get("x-request-id")


def test_relevant_services_rate_limit_only(trace, tracing, label):
    """
    Test that traces with only a RateLimitPolicy include all relevant services (wasm-shim, limitador, and gateway).
    Trace should not contain authorino since no authorization is involved.
    """

    traces = tracing.get_full_trace(request_id=trace, service="wasm-shim", min_processes=3)
    assert len(traces) == 1, f"No trace was found in tracing backend with request_id: {trace}"

    processes = traces[0]["processes"]
    process_services = {process["serviceName"] for process in processes.values()}

    services = ["wasm-shim", "limitador", f"{label}.kuadrant"]
    for service in services:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"

    assert (
        "authorino" not in process_services
    ), f"'authorino' should not be in trace with only RateLimitPolicy: {process_services}"
