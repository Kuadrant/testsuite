"""Test TokenRateLimitPolicy functionality"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


def test_free_tier_key(client, free_user_auth):
    """Ensures a valid free-tier API key returns 200 OK"""
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


def test_paid_tier_key(client, paid_user_auth):
    """Ensures a valid paid-tier API key returns 200 OK"""
    response = client.post(
        "/v1/chat/completions",
        auth=paid_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


def test_invalid_api_key(client):
    """Ensures an invalid API key is rejected with 401 Unauthorized"""
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "APIKEY invalid"},
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_missing_api_key(client):
    """Ensures requests without an API key are rejected with 401 Unauthorized"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "What is Kubernetes?"}],
        },
    )
    assert response is not None
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_token_usage_on_request(client, free_user_auth):
    """Ensures a request with max_tokens=100 returns 200 OK and reports token usage"""
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "Tell me a long story about a Kubernetes"}],
            "max_tokens": 100,
        },
    )

    assert response is not None
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    usage = response.json()["usage"]
    assert usage["total_tokens"] > 0
    assert usage["total_tokens"] <= 100


def test_multiple_requests_under_limit(client, paid_user_auth):
    """Ensures multiple requests within the token quota each return 200 OK"""
    for _ in range(3):
        response = client.post(
            "/v1/chat/completions",
            auth=paid_user_auth,
            json={
                "model": "meta-llama/Llama-3.1-8B-Instruct",
                "messages": [{"role": "user", "content": "What is Kubernetes?"}],
                "max_tokens": 50,
            },
        )
        assert response is not None
        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


def test_token_rate_limit_free_user(client, free_user_auth):
    """Ensures free-tier users are rate limited after exceeding their token quota"""
    total_tokens = 0

    # Make requests until we exceed the token limit
    for i in range(10):
        response = client.post(
            "/v1/chat/completions",
            auth=free_user_auth,
            json={
                "model": "meta-llama/Llama-3.1-8B-Instruct",
                "messages": [{"role": "user", "content": f"Request {i}"}],
                "max_tokens": 30,
                "stream": False,
                "usage": True,
            },
        )

        print(f"Request {i}: {response.status_code}")

        if response.status_code == 200:
            tokens_used = response.json().get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens_used
            print(f"Tokens: {tokens_used}, Total: {total_tokens}")
        elif response.status_code == 429:
            print(f"Rate limited after {total_tokens} tokens (limit: 50)")
            break
        else:
            assert False, f"Unexpected status: {response.status_code}"
    else:
        assert False, f"Rate limit not triggered after {total_tokens} tokens"

    # Next request should be 429
    response = client.post(
        "/v1/chat/completions",
        auth=free_user_auth,
        json={
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5,
            "stream": False,
            "usage": True,
        },
    )
    assert response.status_code == 429, f"Follow-up request should be 429, got {response.status_code}"
