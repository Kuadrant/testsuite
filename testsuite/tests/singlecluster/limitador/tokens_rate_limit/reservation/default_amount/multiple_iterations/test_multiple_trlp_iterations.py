"""Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over multiple iterations"""

import math
from time import sleep
import pytest

from testsuite.utils.constants import TRLP_ITERATION_RESET_WAIT
from .... import CHAT_MESSAGES, MOCK_TOTAL_TOKENS, MODEL, register_chat_completion_mock
from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]


basic_request = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


@pytest.fixture(scope="module", autouse=True)
def chat_completion_mock(mockserver_client):
    """Registers the fixed-usage chat completion mock backing this module's requests"""
    register_chat_completion_mock(mockserver_client)


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_multiple_trlp_limit_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations"""
    # The "200 after reset" check at the end of an iteration consumes MOCK_TOTAL_TOKENS from the
    # window the next iteration reuses, so every iteration but the first starts with one
    # request's worth of budget already spent, and needs one fewer request to hit the limit.
    requests_until_limit = math.ceil(LIMIT.limit / MOCK_TOTAL_TOKENS)

    for i in range(10):
        count = requests_until_limit if i == 0 else requests_until_limit - 1

        for j in range(count):
            response = client.post("/v1/chat/completions", json={**basic_request})
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}/10: Expected 200 on request {j+1}/{count}, got {response.status_code}"

        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}/10: Expected 429 after {count} requests, but got {response.status_code}"

        sleep(TRLP_ITERATION_RESET_WAIT)
        response = client.post("/v1/chat/completions", json={**basic_request})
        assert (
            response.status_code == 200
        ), f"Iteration {i+1}/10: Expected 200 after reset, but got {response.status_code}"
