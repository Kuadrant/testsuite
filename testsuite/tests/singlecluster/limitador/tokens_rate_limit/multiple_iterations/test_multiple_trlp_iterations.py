"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over multiple iterations
"""

from time import sleep
import pytest

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


def test_multiple_trlp_limit_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations"""
    for i in range(10):
        total_tokens = 0

        while total_tokens < LIMIT.limit:
            response = client.post("/v1/chat/completions", json={**basic_request})
            if response.status_code == 429:
                break
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/10: Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"

            tokens_used = response.json()["usage"]["total_tokens"]
            assert tokens_used > 0, f"Got 0 tokens on iteration {i+1}/10"
            total_tokens += tokens_used

        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}/10: Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

        sleep(20)
        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/10: Expected 200 after reset, but got {response.status_code}"
