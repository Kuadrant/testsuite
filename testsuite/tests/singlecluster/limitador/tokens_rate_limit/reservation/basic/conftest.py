"""Conftest for the basic TRLP Reserve/Commit flow tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import Reservation, TokenRateLimitPolicy

LIMIT = Limit(limit=200, window="20s")


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module", params=["route", "gateway"])
def token_rate_limit(request, cluster, blame, module_label, route, gateway):  # pylint: disable=unused-argument
    """Creates TRLP with an explicit token reservation configured on the limit"""
    target_ref = request.getfixturevalue(request.param)

    policy = TokenRateLimitPolicy.create_instance(
        cluster, blame(f"trlp-{request.param}"), target_ref, labels={"testRun": module_label}
    )
    policy.add_limit(name="limit", limits=[LIMIT])
    policy.set_reservation("limit", Reservation(amount=50, ttl='duration("20s")'))
    return policy
