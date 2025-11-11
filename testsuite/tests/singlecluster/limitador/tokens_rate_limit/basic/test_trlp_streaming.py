"""
Test TokenRateLimitPolicy functionality with streaming enabled
"""

import json
from time import sleep

import pytest

from .conftest import FREE_USER_LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.authorino]

streaming_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": True,  # enable streaming
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "stream_options": {"include_usage": True},
    "max_tokens": 15,
}


def parse_streaming_usage(response):
    """Parse the streaming response and return the `usage` object from the last JSON chunk"""
    raw = response.text.strip().splitlines()
    json_lines = [line.removeprefix("data: ").strip() for line in raw if line.startswith("data: {")]
    assert json_lines, f"No JSON chunks found in streaming response:\n{response.text}"
    last_json = json.loads(json_lines[-1])
    usage = last_json.get("usage")
    assert usage and all(
        k in usage for k in ("total_tokens", "prompt_tokens", "completion_tokens")
    ), f"Missing or invalid usage in streaming response: {last_json}"
    return usage


def test_trlp_streaming_limit_and_reset(client, free_user_auth):
    """Ensures users are rate limited and limits reset correctly with streaming enabled"""
    total_tokens = 0

    # Check first request succeeds
    first_response = client.post("/v1/chat/completions", auth=free_user_auth, json={**streaming_request})
    assert first_response.status_code == 200, f"Expected 200, got {first_response.status_code}"
    usage = parse_streaming_usage(first_response)
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    hit_limit = False
    max_requests = 10  # Safety limit to prevent infinite loop
    for request_num in range(max_requests):
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**streaming_request})
        if response.status_code == 429:
            hit_limit = True
            break
        assert (
            response.status_code == 200
        ), f"Request {request_num + 1} got {response.status_code} at {total_tokens}/{FREE_USER_LIMIT.limit} tokens"

        usage = parse_streaming_usage(response)
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    # Verify the rate limit was hit
    assert hit_limit, f"Rate limit was never hit after {total_tokens}/{FREE_USER_LIMIT.limit} tokens"

    sleep(30)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**streaming_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
