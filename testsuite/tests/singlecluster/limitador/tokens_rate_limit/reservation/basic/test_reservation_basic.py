"""
Tests the Reserve/Commit flow of TokenRateLimitPolicy end-to-end through wasm-shim and Limitador,
with an explicit reservation.amount/ttl configured on the limit
"""

from time import sleep

import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from ... import CHAT_MESSAGES, MODEL
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_limit_and_reset(client):
    """Ensures requests succeed until the reservation-enforced limit is reached, then reset after the window"""
    total_tokens = 0

    while total_tokens < LIMIT.limit:
        response = client.post("/v1/chat/completions", json={**basic_request})
        if response.status_code == 429:
            break
        assert (
            response.status_code == 200
        ), f"Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"
        tokens_used = response.json()["usage"]["total_tokens"]
        assert tokens_used > 0, "Got 0 tokens in the response"
        total_tokens += tokens_used

    response = client.post("/v1/chat/completions", json={**basic_request})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

    sleep(TRLP_ITERATION_RESET_WAIT)
    response = client.post("/v1/chat/completions", json={**basic_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
