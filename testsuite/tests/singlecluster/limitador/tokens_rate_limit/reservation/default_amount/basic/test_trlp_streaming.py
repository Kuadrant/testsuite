"""Test TokenRateLimitPolicy functionality with streaming enabled"""

import math
from time import sleep

import pytest

from testsuite.utils.constants import TRLP_FREE_USER_RESET_WAIT
from .... import MOCK_TOTAL_TOKENS, STREAMING_REQUEST, register_streaming_chat_completion_mock
from .conftest import FREE_USER_LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module", autouse=True)
def chat_completion_mock(mockserver_client):
    """Registers the fixed-usage, streaming chat completion mock backing this module's requests"""
    register_streaming_chat_completion_mock(mockserver_client)


@pytest.mark.flaky(reruns=3, reruns_delay=35)
def test_trlp_streaming_limit_and_reset(client, free_user_auth):
    """Ensures users are rate limited and limits reset correctly with streaming enabled"""
    requests_until_limit = math.ceil(FREE_USER_LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(requests_until_limit):
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit}, got {response.status_code}"

    # Next request should be 429
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {requests_until_limit} requests, but got {response.status_code}"

    # Assert quota resets after wait period
    sleep(TRLP_FREE_USER_RESET_WAIT)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
