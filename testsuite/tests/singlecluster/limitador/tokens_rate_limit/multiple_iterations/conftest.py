"""Conftest for TokenRateLimitPolicy multiple iterations tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

LIMIT = Limit(limit=50, window="20s")


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module", params=["route", "gateway"])
def token_rate_limit(request, cluster, blame, module_label):
    """Create basic TRLP"""
    target_ref = request.getfixturevalue(request.param)

    policy = TokenRateLimitPolicy.create_instance(
        cluster, blame(f"trlp-{request.param}"), target_ref, labels={"testRun": module_label}
    )

    policy.add_limit(name="limit", limits=[LIMIT])
    return policy
