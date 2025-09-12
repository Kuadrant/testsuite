"""
Test TokenRateLimitPolicy functionality

TRLP User Guide:
https://docs.kuadrant.io/dev/kuadrant-operator/doc/user-guides/tokenratelimitpolicy/authenticated-token-ratelimiting-tutorial/
"""

from time import sleep
import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.authorino]

basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
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
    limit = 50

    # Check first request succeeds
    first_response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 20})
    assert first_response.status_code == 200, f"Expected status code 200, but got {first_response.status_code}"
    first_json = first_response.json()
    usage = first_json.get("usage")
    assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    # Keep sending requests while within token quota
    while total_tokens <= limit:
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 50})
        if response.status_code == 429:
            break
        assert response.status_code == 200
        json_data = response.json()
        usage = json_data.get("usage")
        assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    # Once over the limit, the next request should be rate limited
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 5})
    assert response.status_code == 429, f"Expected 429 after {total_tokens} tokens, but got {response.status_code}"

    # Assert quota resets after wait period
    sleep(35)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 5})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"


def test_trlp_limit_and_reset_paid_user(client, paid_user_auth):
    """Ensures paid users are rate limited and limits reset correctly"""
    total_tokens = 0
    limit = 100

    first_response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request, "max_tokens": 20})
    assert first_response.status_code == 200, f"Expected status code 200, but got {first_response.status_code}"
    first_json = first_response.json()
    usage = first_json.get("usage")
    assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    while total_tokens <= limit:
        response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request, "max_tokens": 50})
        if response.status_code == 429:
            break
        assert response.status_code == 200
        json_data = response.json()
        usage = json_data.get("usage")
        assert usage and all(key in usage for key in ("total_tokens", "prompt_tokens", "completion_tokens"))
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request, "max_tokens": 5})
    assert response.status_code == 429, f"Expected 429 after {total_tokens} tokens, but got {response.status_code}"

    sleep(65)
    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request, "max_tokens": 5})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
