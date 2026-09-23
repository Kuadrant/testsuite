"""Conftest for TRLP reservation clamping tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import Reservation, TokenRateLimitPolicy

LIMIT = Limit(limit=100, window="20s")
BIG_AMOUNT = 100
SMALL_AMOUNT = 10
BIG_REQUEST_HEADER = "x-reserve-big"

# A single counter whose reservation.amount is a CEL expression, not a flat number: requests
# carrying BIG_REQUEST_HEADER ask for BIG_AMOUNT (the whole limit), everything else asks for
# SMALL_AMOUNT. This lets both sizes race on the same counter so a big reservation's actual
# clamped hold can be revealed by whether a concurrent small reservation still fits.
RESERVATION_AMOUNT_CEL = (
    f'request.headers.exists(h, h.lowerAscii() == "{BIG_REQUEST_HEADER}" && request.headers[h] == "true")'
    f" ? {BIG_AMOUNT} : {SMALL_AMOUNT}"
)


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Creates TRLP with a single counter whose reservation amount varies per request"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit(name="limit", limits=[LIMIT])
    policy.set_reservation("limit", Reservation(amount=RESERVATION_AMOUNT_CEL, ttl='duration("20s")'))
    return policy
