"""Shared fixtures for egress gateway tracing tests."""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.rate_limit import Limit

# Deliberately generous: these tests only need Limitador in the span chain, not an enforced 429.
# A tight limit is fragile here because the client retries 503s while the route is still
# propagating, and those retries consume the counter before the measured request is sent.
LIMIT = Limit(100, "10s")


@pytest.fixture(scope="module", autouse=True)
def require_tracing_enabled(kuadrant, skip_or_fail):
    """Skip or fail tests if tracing is not configured in the Kuadrant CR"""
    tracing_spec = kuadrant.model.spec.get("observability", {}).get("tracing")
    if tracing_spec is None or tracing_spec.get("defaultEndpoint") is None:
        skip_or_fail("Tracing is not configured in Kuadrant CR")


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """API key Secret identifying the test user"""
    return create_api_key("api-key", module_label, "IAMTESTUSER")


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API key auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """AuthPolicy on the egress route, so Authorino produces spans"""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """RateLimitPolicy on the egress route, so Limitador produces spans"""
    rate_limit.add_limit("egress", [LIMIT])
    return rate_limit
