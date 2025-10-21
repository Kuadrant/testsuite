"""
Test TokenRateLimitPolicy functionality

TRLP User Guide:
https://docs.kuadrant.io/dev/kuadrant-operator/doc/user-guides/tokenratelimitpolicy/authenticated-token-ratelimiting-tutorial/
"""

from time import sleep

import pytest

from .conftest import FREE_USER_LIMIT, PAID_USER_LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.authorino]

basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # disable streaming (default)
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 15,
}


def test_invalid_api_key(client):
    """Ensures an invalid API key is rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", headers={"Authorization": "APIKEY invalid"}, json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_missing_api_key(client):
    """Ensures requests without an API key are rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_trlp_limit_and_reset_free_user(client, free_user_auth):
    """Ensures free users are rate limited and limits reset correctly"""
    total_tokens = 0

    # Check first request succeeds
    first_response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
    assert first_response.status_code == 200, f"Expected status code 200, but got {first_response.status_code}"
    first_json = first_response.json()
    usage = first_json.get("usage")
    assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    # Keep sending requests until the rate limit is hit
    hit_limit = False  # Track if the rate limit has been hit (received 429)
    max_requests = 10  # Safety limit to prevent infinite loop
    for request_num in range(max_requests):
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
        if response.status_code == 429:
            hit_limit = True
            break
        assert (
            response.status_code == 200
        ), f"Request {request_num + 1} got {response.status_code} at {total_tokens}/{FREE_USER_LIMIT.limit} tokens"

        # Track token usage
        json_data = response.json()
        usage = json_data.get("usage")
        assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    # Verify the rate limit was hit
    assert hit_limit, f"Rate limit was never hit after {total_tokens}/{FREE_USER_LIMIT.limit} tokens"

    # Assert quota resets after wait period
    sleep(30)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"


def test_trlp_limit_and_reset_paid_user(client, paid_user_auth):
    """Ensures paid users are rate limited and limits reset correctly"""
    total_tokens = 0

    first_response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
    assert first_response.status_code == 200, f"Expected status code 200, but got {first_response.status_code}"
    first_json = first_response.json()
    usage = first_json.get("usage")
    assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    hit_limit = False
    max_requests = 20
    for request_num in range(max_requests):
        response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
        if response.status_code == 429:
            hit_limit = True
            break
        assert (
            response.status_code == 200
        ), f"Request {request_num + 1} got {response.status_code} at {total_tokens}/{PAID_USER_LIMIT.limit} tokens"

        json_data = response.json()
        usage = json_data.get("usage")
        assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    assert hit_limit, f"Rate limit was never hit after {total_tokens}/{PAID_USER_LIMIT.limit} tokens"

    sleep(60)
    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
