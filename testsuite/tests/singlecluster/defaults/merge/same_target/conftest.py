"""Setup conftest for policy merge on the same targets"""

import pytest

from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

LIMIT = Limit(4, "10s")
MERGE_LIMIT = Limit(2, "10s")
MERGE_LIMIT2 = Limit(6, "10s")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    rate_limit.add_limit("basic", [LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.fixture(scope="module")
def default_merge_rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    policy = RateLimitPolicy.create_instance(cluster, blame("dmp"), route, labels={"testRun": module_label})
    policy.defaults.add_limit("basic", [MERGE_LIMIT], when=[CelPredicate("request.path == '/get'")])
    policy.defaults.add_limit("merge", [MERGE_LIMIT2], when=[CelPredicate("request.path == '/anything'")])
    policy.defaults.strategy(Strategy.MERGE)
    return policy
