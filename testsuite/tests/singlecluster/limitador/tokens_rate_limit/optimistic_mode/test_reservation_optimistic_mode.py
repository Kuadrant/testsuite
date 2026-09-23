"""
Tests that setting Kuadrant CR spec.tokenRateLimiting.mode to Optimistic opts a cluster out of
reservations and falls back to the legacy Check/Report enforcement flow
"""

import pytest

from .. import CHAT_MESSAGES, MODEL
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.disruptive]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_optimistic_mode_rate_limits(client):
    """Ensures the limit is still enforced via Check/Report when the cluster is in Optimistic mode"""
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
