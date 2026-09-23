"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over
multiple iterations with streaming enabled
"""

from time import sleep

import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from .... import STREAMING_REQUEST, parse_streaming_usage
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_multiple_trlp_streaming_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations with streaming enabled"""
    for i in range(5):
        total_tokens = 0

        while total_tokens < LIMIT.limit:
            response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
            if response.status_code == 429:
                break
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/5: Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"

            usage = parse_streaming_usage(response)
            tokens_used = usage["total_tokens"]
            assert tokens_used > 0, f"Got 0 tokens on iteration {i+1}/5"
            total_tokens += tokens_used

        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}/5: Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

        sleep(TRLP_ITERATION_RESET_WAIT)
        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/5: Expected 200 after reset, but got {response.status_code}"
