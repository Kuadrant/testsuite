"""Setup conftest for policy merge tests"""

import pytest

from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def route(backend, route):
    """Add 2 backend rules for specific backend paths"""
    route.add_backend(backend, "/image")
    return route


@pytest.fixture(scope="module")
def global_rate_limit(cluster, blame, module_label, gateway):
    """Create a RateLimitPolicy with default policies and a merge strategy."""
    global_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("omp"), gateway, labels={"testRun": module_label}
    )
    gateway_limit = CelPredicate("request.path == '/get'")
    global_rate_limit.overrides.add_limit("gateway_limit", [Limit(5, "10s")], when=[gateway_limit])
    anything_when = CelPredicate("request.path == '/anything'")
    global_rate_limit.overrides.add_limit("anything_limit", [Limit(10, "5s")], when=[anything_when])
    global_rate_limit.overrides.strategy(Strategy.MERGE)
    return global_rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, global_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [global_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()
