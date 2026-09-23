"""Conftest for TRLP reservation concurrency tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import Reservation, TokenRateLimitPolicy

LIMIT = Limit(limit=100, window="20s")
RESERVATION_AMOUNT = 50  # matches Limitador's default 50% max-reservation-fraction of LIMIT.limit


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Creates TRLP with a reservation large enough that a few concurrent requests exhaust the limit"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit(name="limit", limits=[LIMIT])
    policy.set_reservation("limit", Reservation(amount=RESERVATION_AMOUNT, ttl='duration("20s")'))
    return policy
