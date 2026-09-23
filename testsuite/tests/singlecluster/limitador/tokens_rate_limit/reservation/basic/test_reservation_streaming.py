"""
Tests the Reserve/Commit flow of TokenRateLimitPolicy with streaming enabled
"""

from time import sleep

import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from ... import STREAMING_REQUEST, parse_streaming_usage
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_streaming_limit_and_reset(client):
    """Ensures the reservation-enforced limit is enforced and resets correctly with streaming enabled"""
    total_tokens = 0

    while total_tokens < LIMIT.limit:
        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        if response.status_code == 429:
            break
        assert (
            response.status_code == 200
        ), f"Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"
        usage = parse_streaming_usage(response)
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0, "Got 0 tokens in the response"
        total_tokens += tokens_used

    response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

    sleep(TRLP_ITERATION_RESET_WAIT)
    response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
