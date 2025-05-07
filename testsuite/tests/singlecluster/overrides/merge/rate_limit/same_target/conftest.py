"""Setup conftest for policy override on the same targets"""

import pytest

from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

LIMIT = Limit(4, "5s")
OVERRIDE_LIMIT = Limit(6, "5s")
OVERRIDE_LIMIT2 = Limit(2, "5s")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    rate_limit.add_limit("basic", [LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.fixture(scope="module")
def override_merge_rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    policy = RateLimitPolicy.create_instance(cluster, blame("omp"), route, labels={"testRun": module_label})
    policy.overrides.add_limit("basic", [OVERRIDE_LIMIT], when=[CelPredicate("request.path == '/get'")])
    policy.overrides.add_limit("override", [OVERRIDE_LIMIT2], when=[CelPredicate("request.path == '/anything'")])
    policy.overrides.strategy(Strategy.MERGE)
    return policy
