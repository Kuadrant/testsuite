"""
Tests that per-user token reservations are isolated: one user hitting their limit
does not affect another user's independent counter
"""

import pytest

from ... import CHAT_MESSAGES, MODEL
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_isolated_per_user(client, user1_auth, user2_auth):
    """Ensures user1 hitting their reservation-enforced limit does not rate limit user2"""
    total_tokens = 0

    while total_tokens < LIMIT.limit:
        response = client.post("/v1/chat/completions", auth=user1_auth, json={**basic_request})
        if response.status_code == 429:
            break
        assert (
            response.status_code == 200
        ), f"Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"
        tokens_used = response.json()["usage"]["total_tokens"]
        assert tokens_used > 0, "Got 0 tokens in the response"
        total_tokens += tokens_used

    response = client.post("/v1/chat/completions", auth=user1_auth, json={**basic_request})
    assert (
        response.status_code == 429
    ), f"Expected user1 to be rate limited after {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"

    response = client.post("/v1/chat/completions", auth=user2_auth, json={**basic_request})
    assert response.status_code == 200, f"Expected user2 unaffected by user1's limit, got {response.status_code}"
