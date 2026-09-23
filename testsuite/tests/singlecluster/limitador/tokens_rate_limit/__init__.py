"""Tests for TokenRateLimitPolicy"""

import json

MODEL = "meta-llama/Llama-3.1-8B-Instruct"

CHAT_MESSAGES = [{"role": "user", "content": "What is Kubernetes?"}]

STREAMING_REQUEST = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
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
