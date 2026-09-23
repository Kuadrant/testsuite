"""
Tests that Limitador clamps an oversized reservation.amount down to its default
--max-reservation-fraction (50% of the counter's limit), instead of honoring the full request.

A single TRLP counter's reservation.amount varies per request via a CEL expression: a request
carrying a marker header asks for the whole limit (BIG_AMOUNT), everything else asks for a
small amount (SMALL_AMOUNT) that easily fits within 50% of the limit. The first big request is
sent alone and given a short head start, then a second big request and a small request are
fired together - short enough that the first big reservation is still only just admitted (not
yet committed) but definitely already reserved before the other two fire. This guarantees the
first big request is always admitted, and the second big request is always rejected by it (a
second full-limit ask never fits once anything is held) - regardless of clamping. The small
request's fate is what actually depends on clamping: if the first big reservation only ever
holds 50% of the limit as documented, the small request still fits in what's left and is
admitted. If it held its full requested amount instead, the small request would be rejected too.
"""

from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pytest

from ... import CHAT_MESSAGES, MODEL
from .conftest import BIG_AMOUNT, BIG_REQUEST_HEADER, LIMIT, SMALL_AMOUNT

pytestmark = [pytest.mark.limitador]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 15,
}

# Just long enough to bias the first big request's fast, local Reserve call ahead of the other
# two, but far short of a full request round trip (Reserve + backend + Commit), so it stays
# merely reserved (not yet committed) when the other two requests fire.
FIRST_REQUEST_HEAD_START = 0.1


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_amount_is_clamped_to_max_fraction(client):
    """Ensures a concurrent small reservation still fits once the first big reservation only holds half"""
    assert BIG_AMOUNT > LIMIT.limit // 2 >= SMALL_AMOUNT, "Test setup error: amounts must straddle the 50% cap"

    big_headers = {BIG_REQUEST_HEADER: "true"}

    with ThreadPoolExecutor(max_workers=3) as pool:
        first_big_future = pool.submit(client.post, "/v1/chat/completions", headers=big_headers, json={**basic_request})
        sleep(FIRST_REQUEST_HEAD_START)
        second_big_future = pool.submit(
            client.post, "/v1/chat/completions", headers=big_headers, json={**basic_request}
        )
        small_future = pool.submit(client.post, "/v1/chat/completions", json={**basic_request})

        first_big_status = first_big_future.result().status_code
        second_big_status = second_big_future.result().status_code
        small_status = small_future.result().status_code

    assert first_big_status == 200, f"Expected the first big reservation admitted, got {first_big_status}"
    assert second_big_status == 429, (
        "Expected the second big reservation to be rejected once anything is already held, " f"got {second_big_status}"
    )
    assert small_status == 200, (
        "Expected the small reservation to be admitted, proving the first big reservation was clamped to "
        f"{LIMIT.limit // 2} tokens rather than holding the full {BIG_AMOUNT} it requested; got {small_status}"
    )
