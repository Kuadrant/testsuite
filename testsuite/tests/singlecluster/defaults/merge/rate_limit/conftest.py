"""Conftest for overrides merge strategy tests for AuthPolicies"""

import pytest

from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

LIMIT = Limit(4, "10s")
MERGE_LIMIT = Limit(2, "10s")
MERGE_LIMIT2 = Limit(6, "10s")


@pytest.fixture(scope="module")
def route(backend, route):
    """Add 2 backend rules for specific backend paths"""
    route.add_backend(backend, "/image")
    return route


@pytest.fixture(scope="module")
def global_rate_limit(request, metrics_route, cluster, blame, module_label):
    """Create a RateLimitPolicy with default policies and a merge strategy."""
    target_ref = request.getfixturevalue(getattr(request, "param", "gateway"))

    policy = RateLimitPolicy.create_instance(cluster, blame("dmp"), target_ref, labels={"testRun": module_label})
    policy.defaults.add_limit("get_limit", [MERGE_LIMIT], when=[CelPredicate("request.path == '/get'")])
    policy.defaults.add_limit("anything_limit", [MERGE_LIMIT2], when=[CelPredicate("request.path == '/anything'")])
    policy.defaults.strategy(Strategy.MERGE)
    policy.set_metrics_route(metrics_route)
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(
    request,
    route,
    global_rate_limit,
    rate_limit,
):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [global_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()
