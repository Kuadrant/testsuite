"""Conftest for "identical hostname" tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to 1st RateLimitPolicy allowing 1 request per 10 seconds (a.k.a. '1rp10s' RateLimitPolicy)"""
    rate_limit.add_limit("1rp10s", [Limit(1, "10s")])
    return rate_limit
