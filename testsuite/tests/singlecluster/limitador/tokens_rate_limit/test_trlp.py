"""Test TokenRateLimitPolicy functionality"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


BASIC_REQUEST = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
}


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_free_tier_key(client, free_user_auth):
    """Ensures a valid free-tier API key returns 200 OK"""
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json=BASIC_REQUEST,
    )
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_paid_tier_key(client, paid_user_auth):
    """Ensures a valid paid-tier API key returns 200 OK"""
    response = client.post(
        "/v1/chat/completions",
        auth=paid_user_auth,
        json=BASIC_REQUEST,
    )
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_invalid_api_key(client):
    """Ensures an invalid API key is rejected with 401 Unauthorized"""
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "APIKEY invalid"},
        json=BASIC_REQUEST,
    )
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_missing_api_key(client):
    """Ensures requests without an API key are rejected with 401 Unauthorized"""
    response = client.post(
        "/v1/chat/completions",
        json=BASIC_REQUEST,
    )
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_token_usage_on_request(client, free_user_auth):
    """Ensures a request with max_tokens=100 returns 200 OK and reports token usage"""
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={**BASIC_REQUEST, "max_tokens": 100},
    )
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    usage = response.json()["usage"]
    assert usage["total_tokens"] > 0
    assert usage["total_tokens"] <= 100


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_multiple_requests_under_limit(client, paid_user_auth):
    """Ensures multiple requests within the token quota each return 200 OK"""
    for _ in range(3):
        response = client.post(
            "/v1/chat/completions",
            auth=paid_user_auth,
            json={**BASIC_REQUEST, "max_tokens": 50},
        )
        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_token_rate_limit_free_user(client, free_user_auth):
    """Ensures free-tier users are rate limited after exceeding their token quota"""
    total_tokens = 0

    # Make requests until they exceed the token limit
    for _ in range(10):
        response = client.post(
            "/v1/chat/completions",
            auth=free_user_auth,
            json={**BASIC_REQUEST, "max_tokens": 30, "stream": False, "usage": True},
        )
        if response.status_code == 429:
            break

        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

        tokens_used = response.json().get("usage", {}).get("total_tokens", 0)
        total_tokens += tokens_used

    else:
        assert False, f"Rate limit not triggered after {total_tokens} tokens"

    # Next request should be 429
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={**BASIC_REQUEST, "max_tokens": 5, "stream": False, "usage": True},
    )
    assert response.status_code == 429, f"Follow-up request should be 429, but got {response.status_code}"


@pytest.mark.parametrize("token_rate_limit", ["route", "gateway"], indirect=True)
def test_token_rate_limit_paid_user(client, paid_user_auth):
    """Ensures paid-tier users are rate limited after exceeding their token quota"""
    total_tokens = 0

    for _ in range(20):
        response = client.post(
            "/v1/chat/completions",
            auth=paid_user_auth,
            json={**BASIC_REQUEST, "max_tokens": 30, "stream": False, "usage": True},
        )
        if response.status_code == 429:
            break

        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

        tokens_used = response.json().get("usage", {}).get("total_tokens", 0)
        total_tokens += tokens_used

    else:
        assert False, f"Rate limit not triggered after {total_tokens} tokens"

    response = client.post(
        "/v1/chat/completions",
        auth=paid_user_auth,
        json={**BASIC_REQUEST, "max_tokens": 5, "stream": False, "usage": True},
    )
    assert response.status_code == 429, f"Follow-up request should be 429, but got {response.status_code}"
