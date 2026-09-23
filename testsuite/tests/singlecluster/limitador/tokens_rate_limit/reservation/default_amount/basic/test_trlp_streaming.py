"""Test TokenRateLimitPolicy functionality with streaming enabled"""

from time import sleep

import pytest

from testsuite.utils.constants import TRLP_FREE_USER_RESET_WAIT
from .... import STREAMING_REQUEST, parse_streaming_usage
from .conftest import FREE_USER_LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.mark.flaky(reruns=3, reruns_delay=35)
def test_trlp_streaming_limit_and_reset(client, free_user_auth):
    """Ensures users are rate limited and limits reset correctly with streaming enabled"""
    total_tokens = 0

    # Check first request succeeds
    first_response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
    assert first_response.status_code == 200, f"Expected 200, got {first_response.status_code}"
    usage = parse_streaming_usage(first_response)
    tokens_used = usage["total_tokens"]
    assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
    total_tokens += tokens_used

    # Keep sending requests while within token quota
    while total_tokens < FREE_USER_LIMIT.limit:
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
        assert response.status_code == 200
        usage = parse_streaming_usage(response)
        tokens_used = usage["total_tokens"]
        assert tokens_used > 0 and tokens_used == usage["prompt_tokens"] + usage["completion_tokens"]
        total_tokens += tokens_used

    # Next request should be 429
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
    assert (
        response.status_code == 429
    ), f"Expected 429 after {total_tokens}/{FREE_USER_LIMIT.limit} tokens, but got {response.status_code}"

    # Assert quota resets after wait period
    sleep(TRLP_FREE_USER_RESET_WAIT)
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**STREAMING_REQUEST})
    assert response.status_code == 200, f"Expected 200 after reset, but got {response.status_code}"
