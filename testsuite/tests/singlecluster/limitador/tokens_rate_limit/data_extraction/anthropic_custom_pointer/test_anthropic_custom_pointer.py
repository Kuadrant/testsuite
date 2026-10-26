"""
Verifies an explicit dataExtraction.response.totalTokens pointer lets TokenRateLimitPolicy count
usage from Anthropic's Messages API response shape, which is not covered by the built-in defaults
(RFC 0024) since Anthropic has no native total-tokens field.
"""

import math

import pytest
from mockserver.llm import Completion, Provider, Usage

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]

PATH = "/v1/messages"
MODEL = "claude-sonnet-4-20250514"
INPUT_TOKENS = 15
OUTPUT_TOKENS = 7


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_custom_pointer_extracts_anthropic_usage(client, mockserver_client):
    """The custom pointer must resolve output_tokens from a real Anthropic Messages response"""
    mockserver_client.create_llm_response_expectation(
        "trlp-anthropic",
        PATH,
        Provider.ANTHROPIC,
        completion=Completion(
            text="mocked response",
            stop_reason="end_turn",
            usage=Usage(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
        ),
        model=MODEL,
    )

    requests_until_limit = math.ceil(LIMIT.limit / OUTPUT_TOKENS)
    for i in range(requests_until_limit):
        response = client.post(PATH, json={"model": MODEL})
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit}, got {response.status_code}"

    response = client.post(PATH, json={"model": MODEL})
    assert response.status_code == 429, (
        f"Expected 429 after {requests_until_limit} counted requests (via custom "
        f"/usage/output_tokens pointer), got {response.status_code}"
    )
