"""
Tests that a TRLP limit's reservation config is ignored while the Kuadrant CR is in Optimistic
mode: an oversized reservation.amount (the full limit, which would clamp and block concurrent
requests under Reservation mode - see reservation/clamping/) has no effect here, since
Optimistic mode enforces purely via Check/Report on real, already-reported usage.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from testsuite.kuadrant.policy.token_rate_limit import Reservation, TokenRateLimitPolicy
from .. import CHAT_MESSAGES, MODEL
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.disruptive]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 15,
}

CONCURRENT_REQUESTS = 3


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Creates a TRLP whose limit sets an oversized reservation config, to prove it has no effect here"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit(name="limit", limits=[LIMIT])
    policy.set_reservation("limit", Reservation(amount=LIMIT.limit, ttl='duration("20s")'))
    return policy


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_optimistic_mode_ignores_reservation_config(client):
    """Ensures an oversized reservation.amount does not block concurrent requests in Optimistic mode"""
    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        futures = [
            pool.submit(client.post, "/v1/chat/completions", json={**basic_request}) for _ in range(CONCURRENT_REQUESTS)
        ]
        status_codes = [future.result().status_code for future in futures]

    assert status_codes == [200] * CONCURRENT_REQUESTS, (
        "Expected all concurrent requests admitted - Optimistic mode should enforce purely via Check/Report on "
        f"real usage and ignore the limit's oversized reservation config; got status codes: {status_codes}"
    )
