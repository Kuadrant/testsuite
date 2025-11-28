"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over
multiple iterations with streaming enabled
"""

import json
from time import sleep

import pytest

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


streaming_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": True,  # enable streaming mode
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "stream_options": {"include_usage": True},
    "max_tokens": 15,
}


def parse_streaming_usage(response):
    """
    Take a streaming API response and pull out the final usage statistics.

    The response comes in small chunks of text, each starting with "data: {...}".
    This function looks through all those chunks, finds the last one, and returns
    the "usage" section from it. The usage contains the total, prompt, and
    completion token counts.

    Raises an error if no usage information is found.
    """
    raw = response.text.strip().splitlines()
    json_lines = [line.removeprefix("data: ").strip() for line in raw if line.startswith("data: {")]
    assert json_lines, f"No JSON chunks found in streaming response:\n{response.text}"
    last_json = json.loads(json_lines[-1])
    usage = last_json.get("usage")
    assert usage and all(
        k in usage for k in ("total_tokens", "prompt_tokens", "completion_tokens")
    ), f"Missing or invalid usage in streaming response: {last_json}"
    return usage


def test_multiple_trlp_streaming_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations with streaming enabled"""
    for i in range(5):
        total_tokens = 0

        while total_tokens < LIMIT.limit:
            response = client.post("/v1/chat/completions", json={**streaming_request})
            if response.status_code == 429:
                break
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/5: Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"

            usage = parse_streaming_usage(response)
            tokens_used = usage["total_tokens"]
            assert tokens_used > 0, f"Got 0 tokens on iteration {i+1}/5"
            total_tokens += tokens_used

        response = client.post("/v1/chat/completions", json={**streaming_request})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}/5: Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

        sleep(20)
        response = client.post("/v1/chat/completions", json={**streaming_request})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/5: Expected 200 after reset, but got {response.status_code}"
