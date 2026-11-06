"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over
multiple iterations with streaming enabled
"""

import math
from time import sleep

import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from .... import MOCK_TOTAL_TOKENS, STREAMING_REQUEST, register_streaming_chat_completion_mock
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def chat_completion_mock(mockserver_client):
    """Registers the fixed-usage, streaming chat completion mock backing this module's requests"""
    register_streaming_chat_completion_mock(mockserver_client)


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_multiple_trlp_streaming_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations with streaming enabled"""
    # The "200 after reset" check at the end of an iteration consumes MOCK_TOTAL_TOKENS from the
    # window the next iteration reuses, so every iteration but the first starts with one
    # request's worth of budget already spent, and needs one fewer request to hit the limit.
    requests_until_limit = math.ceil(LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(5):
        count = requests_until_limit if i == 0 else requests_until_limit - 1

        for j in range(count):
            response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/5: Expected 200 on request {j+1}/{count}, got {response.status_code}"

        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}/5: Expected 429 after {count} requests, but got {response.status_code}"

        sleep(TRLP_ITERATION_RESET_WAIT)
        response = client.post("/v1/chat/completions", json={**STREAMING_REQUEST})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/5: Expected 200 after reset, but got {response.status_code}"
