"""Conftest for defaults merge strategy tests for RateLimitPolicies on same target"""

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.tests.singlecluster.defaults.merge.rate_limit.conftest import LIMIT


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit.add_limit("get_limit", [LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit
