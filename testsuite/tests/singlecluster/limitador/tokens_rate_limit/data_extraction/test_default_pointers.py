"""
Verifies TokenRateLimitPolicy's built-in default totalTokens JSON Pointer candidates (RFC 0024)
extract usage from OpenAI, Gemini, streaming OpenAI Responses API, and AWS Bedrock Converse
response shapes, with no explicit `dataExtraction` on the policy.

Gemini covers both flat-JSON and SSE streaming, since its default pointer documents both modes.
Plain OpenAI Chat Completions streaming is skipped: the default list only documents streaming
support for the Responses API, and this suite's MockServer image never emits a usage chunk for
streamed `/v1/chat/completions` anyway.

Bedrock is hand-crafted JSON rather than MockServer's `Provider.BEDROCK`, which actually emits the
older Anthropic-on-Bedrock InvokeModel shape (no `total_tokens`), not the real Converse API.

See the default pointer list:
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/reference/tokenratelimitpolicy.md#token-usage-tracking
"""

import pytest
from mockserver.llm import Completion, Provider, Usage

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]

INPUT_TOKENS = 5
OUTPUT_TOKENS = 5
TOTAL_TOKENS = INPUT_TOKENS + OUTPUT_TOKENS  # deterministic per request, since the mock controls usage directly

BEDROCK_PATH = "/model/amazon.titan-text-express-v1/converse"
BEDROCK_MODEL = "amazon.titan-text-express-v1"

# (provider, path, model, streaming) mirrors MockServer's documented "Typical API path" per provider:
# https://www.mock-server.com/mock_server/llm_response_mocking.html
PROVIDERS = [
    pytest.param("openai", Provider.OPENAI, "/v1/chat/completions", "gpt-4o", False, id="openai"),
    pytest.param(
        "gemini",
        Provider.GEMINI,
        "/v1beta/models/gemini-2.0-flash:generateContent",
        "gemini-2.0-flash",
        False,
        id="gemini",
    ),
    pytest.param(
        "gemini-stream",
        Provider.GEMINI,
        "/v1beta/models/gemini-2.0-flash:generateContent",
        "gemini-2.0-flash",
        True,
        id="gemini-streaming",
    ),
    pytest.param(
        "openai-responses-stream",
        Provider.OPENAI_RESPONSES,
        "/v1/responses",
        "gpt-4o",
        True,
        id="openai-responses-streaming",
    ),
]


def _assert_tokens_rate_limited(client, path, model, headers, provider_label):
    """Exhausts LIMIT at TOTAL_TOKENS/request, then asserts the next request is rate limited"""
    total_tokens = 0
    while total_tokens < LIMIT.limit:
        response = client.post(path, json={"model": model}, headers=headers)
        if response.status_code == 429:
            break
        assert (
            response.status_code == 200
        ), f"Expected 200 on {total_tokens}/{LIMIT.limit} tokens for {provider_label}, got {response.status_code}"
        total_tokens += TOTAL_TOKENS

    response = client.post(path, json={"model": model}, headers=headers)
    assert response.status_code == 429, (
        f"Expected 429 for {provider_label} after {total_tokens}/{LIMIT.limit} tokens (default totalTokens "
        f"pointer should have extracted usage from the {provider_label} response shape), got {response.status_code}"
    )


@pytest.mark.flaky(reruns=3, reruns_delay=25)
@pytest.mark.parametrize("mock_provider,llm_provider,path,model,streaming", PROVIDERS)
def test_default_pointer_extracts_usage(client, mockserver_client, mock_provider, llm_provider, path, model, streaming):
    """Each provider's native wire shape must be recognized by the built-in default pointer list"""
    mockserver_client.clear_expectations_at_path(path)
    mockserver_client.create_llm_response_expectation(
        f"trlp-{mock_provider}",
        path,
        llm_provider,
        completion=Completion(
            text="mocked response",
            usage=Usage(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
            streaming=streaming,
        ),
        model=model,
    )
    _assert_tokens_rate_limited(client, path, model, {"x-mock-provider": mock_provider}, llm_provider)


@pytest.mark.flaky(reruns=3, reruns_delay=25)
def test_default_pointer_extracts_bedrock_usage(client, mockserver_client):
    """The default /usage/totalTokens pointer must resolve a real AWS Bedrock Converse response"""
    # TODO: MockServer has merged a fix (https://github.com/mock-server/mockserver-monorepo/discussions/2757)
    # making Provider.BEDROCK emit the real Converse shape. Once a MockServer release containing it is
    # picked up by this test suite's mockserver image, drop this hand-crafted create_json_expectation
    # and switch to create_llm_response_expectation(..., Provider.BEDROCK, ...) like the other providers.
    mockserver_client.create_json_expectation(
        "trlp-bedrock",
        BEDROCK_PATH,
        body={
            "output": {"message": {"role": "assistant", "content": [{"text": "mocked response"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": INPUT_TOKENS, "outputTokens": OUTPUT_TOKENS, "totalTokens": TOTAL_TOKENS},
        },
    )
    _assert_tokens_rate_limited(client, BEDROCK_PATH, BEDROCK_MODEL, {"x-mock-provider": "bedrock"}, "BEDROCK")
