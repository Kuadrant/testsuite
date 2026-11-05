"""
Tests the Reserve/Commit flow of TokenRateLimitPolicy with streaming enabled
"""

from time import sleep

import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from ... import MOCK_TOTAL_TOKENS, STREAMING_REQUEST, register_streaming_chat_completion_mock
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def chat_completion_mock(mockserver_client):
    """Registers the fixed-usage, streaming chat completion mock backing this module's requests"""
    register_streaming_chat_completion_mock(mockserver_client)


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_reservation_streaming_limit_and_reset(client):
    """Ensures the reservation-enforced limit is enforced and resets correctly with streaming enabled"""
    total_tokens = 0

    while total_tokens < LIMIT.limit:
        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        if response.status_code == 429:
            break
        assert (
            response.status_code == 200
        ), f"Expected 200 on {total_tokens}/{LIMIT.limit} tokens, got {response.status_code}"
        total_tokens += MOCK_TOTAL_TOKENS

    response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {total_tokens}/{LIMIT.limit} tokens, but got {response.status_code}"

    sleep(TRLP_ITERATION_RESET_WAIT)
    response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
