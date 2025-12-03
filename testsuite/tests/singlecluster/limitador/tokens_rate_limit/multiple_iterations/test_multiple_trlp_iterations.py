"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over multiple iterations
"""

from time import sleep
import pytest

from .conftest import LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


def test_multiple_trlp_limit_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations"""
    for i in range(5):
        total_tokens = 0
        hit_limit = False  # Track if the rate limit has been hit (received 429)
        max_requests = 20  # Safety limit to prevent infinite loop

        # Keep sending requests until the rate limit is hit
        for request_num in range(max_requests):
            response = client.post("/v1/chat/completions", json={**basic_request})
            if response.status_code == 429:
                hit_limit = True
                break
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/5: Expected 200 on {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

            usage = response.json().get("usage")
            assert usage, f"Iteration {i+1}/5: No usage in response"
            tokens_used = usage["total_tokens"]
            assert tokens_used > 0, f"Iteration {i+1}/5: Got 0 tokens in request {request_num+1}"
            total_tokens += tokens_used

        # Verify the rate limit was hit
        assert hit_limit, f"Iteration {i+1}/5: Rate limit was never hit after {total_tokens}/{LIMIT.limit} tokens"

        # Wait for rate limit to reset
        sleep(20)

        # Next request should be 429
        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/5: Expected 200 after reset, but got {response.status_code}"
