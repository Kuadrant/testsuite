"""
Test TokenRateLimitPolicy functionality

TRLP User Guide:
https://docs.kuadrant.io/dev/kuadrant-operator/doc/user-guides/tokenratelimitpolicy/authenticated-token-ratelimiting-tutorial/
"""

import math
from time import sleep

import pytest

from testsuite.utils.constants import TRLP_FREE_USER_RESET_WAIT, TRLP_PAID_USER_RESET_WAIT
from .... import CHAT_MESSAGES, MOCK_TOTAL_TOKENS, MODEL, register_chat_completion_mock
from .conftest import FREE_USER_LIMIT, PAID_USER_LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # disable streaming (default)
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 15,
}


@pytest.fixture(scope="module", autouse=True)
def chat_completion_mock(mockserver_client):
    """Registers the fixed-usage chat completion mock backing this module's requests"""
    register_chat_completion_mock(mockserver_client)


def test_invalid_api_key(client):
    """Ensures an invalid API key is rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", headers={"Authorization": "APIKEY invalid"}, json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_missing_api_key(client):
    """Ensures requests without an API key are rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


@pytest.mark.flaky(reruns=3, reruns_delay=35)
def test_trlp_limit_and_reset_free_user(client, free_user_auth):
    """Ensures free users are rate limited and limits reset correctly"""
    requests_until_limit = math.ceil(FREE_USER_LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(requests_until_limit):
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit}, got {response.status_code}"

    # Next request should be 429
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {requests_until_limit} requests, but got {response.status_code}"

    # Assert quota resets after wait period
    sleep(TRLP_FREE_USER_RESET_WAIT)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"


@pytest.mark.flaky(reruns=3, reruns_delay=65)
def test_trlp_limit_and_reset_paid_user(client, paid_user_auth):
    """Ensures paid users are rate limited and limits reset correctly"""
    requests_until_limit = math.ceil(PAID_USER_LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(requests_until_limit):
        response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit}, got {response.status_code}"

    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {requests_until_limit} requests, but got {response.status_code}"

    sleep(TRLP_PAID_USER_RESET_WAIT)
    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
