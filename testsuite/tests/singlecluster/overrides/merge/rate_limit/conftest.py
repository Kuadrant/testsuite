"""Setup conftest for policy merge tests"""

import pytest

from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

LIMIT = Limit(4, "10s")
OVERRIDE_LIMIT = Limit(2, "10s")
OVERRIDE_LIMIT2 = Limit(6, "10s")


@pytest.fixture(scope="module")
def route(backend, route):
    """Add 2 backend rules for specific backend paths"""
    route.add_backend(backend, "/image")
    return route


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    rate_limit.add_limit("get_limit", [LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.fixture(scope="module")
def global_rate_limit(request, cluster, blame, module_label):
    """Create a RateLimitPolicy with default policies and a merge strategy."""
    target_ref = request.getfixturevalue(getattr(request, "param", "gateway"))

    policy = RateLimitPolicy.create_instance(cluster, blame("omp"), target_ref, labels={"testRun": module_label})
    policy.overrides.add_limit("get_limit", [OVERRIDE_LIMIT], when=[CelPredicate("request.path == '/get'")])
    policy.overrides.add_limit("anything_limit", [OVERRIDE_LIMIT2], when=[CelPredicate("request.path == '/anything'")])
    policy.overrides.strategy(Strategy.MERGE)
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, global_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [global_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()
