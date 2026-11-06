"""
Tests that setting Kuadrant CR spec.tokenRateLimiting.mode to Optimistic opts a cluster out of
reservations and falls back to the legacy Check/Report enforcement flow
"""

import math

import pytest

from .. import CHAT_MESSAGES, MOCK_TOTAL_TOKENS, MODEL
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
    requests_until_limit = math.ceil(LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(requests_until_limit):
        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit}, got {response.status_code}"

    response = client.post("/v1/chat/completions", json={**basic_request})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {requests_until_limit} requests, but got {response.status_code}"
