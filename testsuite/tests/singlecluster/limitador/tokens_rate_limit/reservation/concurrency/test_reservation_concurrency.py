"""
Tests that Reserve/Commit closes the check/report race window: concurrent requests are
admitted or rejected based on reserved (not yet committed) capacity, before any request's
actual token usage is known. Under the old Check/Report flow this race would let every
concurrent request through, since none of them see each other's usage until after the fact.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from ... import CHAT_MESSAGES, MODEL
from .conftest import LIMIT, RESERVATION_AMOUNT

pytestmark = [pytest.mark.limitador]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 15,
}

# More concurrent requests than the reservation capacity allows, so at least one must be
# rejected purely on reserved capacity, regardless of how little actual usage is ever reported.
MAX_ADMITTED = LIMIT.limit // RESERVATION_AMOUNT
CONCURRENT_REQUESTS = MAX_ADMITTED + 1


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_rejects_concurrent_overcommit(client):
    """Fires concurrent requests exceeding reservation capacity and expects at least one rejection"""
    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        futures = [
            pool.submit(client.post, "/v1/chat/completions", json={**basic_request}) for _ in range(CONCURRENT_REQUESTS)
        ]
        status_codes = [future.result().status_code for future in futures]

    assert status_codes.count(200) <= MAX_ADMITTED, (
        f"Expected at most {MAX_ADMITTED} of {CONCURRENT_REQUESTS} concurrent requests to be admitted "
        f"by the {RESERVATION_AMOUNT}-token reservation, got status codes: {status_codes}"
    )
    assert (
        429 in status_codes
    ), f"Expected at least one concurrent request rejected by reservation, got status codes: {status_codes}"
