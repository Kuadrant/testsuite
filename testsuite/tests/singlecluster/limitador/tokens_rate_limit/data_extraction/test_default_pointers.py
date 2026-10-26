"""
Verifies TokenRateLimitPolicy's built-in default totalTokens JSON Pointer candidates (RFC 0024)
extract usage from OpenAI, Gemini, streaming OpenAI Responses API, and AWS Bedrock Converse
response shapes, with no explicit `dataExtraction` on the policy.

Gemini covers both flat-JSON and SSE streaming, since its default pointer documents both modes.
Plain OpenAI Chat Completions streaming is skipped: the default list only documents streaming
support for the Responses API, and this suite's MockServer image never emits a usage chunk for
streamed `/v1/chat/completions` anyway.

See the default pointer list:
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/reference/tokenratelimitpolicy.md#token-usage-tracking
"""

import math

import pytest
from mockserver.llm import Completion, Provider, Usage

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]

INPUT_TOKENS = 5
OUTPUT_TOKENS = 5
TOTAL_TOKENS = INPUT_TOKENS + OUTPUT_TOKENS  # deterministic per request, since the mock controls usage directly

# (mock_provider, llm_provider, path, model, streaming, query) mirrors MockServer's documented
# "Typical API path" per provider: https://www.mock-server.com/mock_server/llm_response_mocking.html
# Gemini streaming needs the real `:streamGenerateContent` route plus `?alt=sse` to get MockServer
# to emit actual SSE chunks - `streaming=True` on the Completion alone is not enough.
PROVIDERS = [
    pytest.param("openai", Provider.OPENAI, "/v1/chat/completions", "gpt-4o", False, None, id="openai"),
    pytest.param(
        "gemini",
        Provider.GEMINI,
        "/v1beta/models/gemini-2.0-flash:generateContent",
        "gemini-2.0-flash",
        False,
        None,
        id="gemini",
    ),
    pytest.param(
        "gemini-stream",
        Provider.GEMINI,
        "/v1beta/models/gemini-2.0-flash:streamGenerateContent",
        "gemini-2.0-flash",
        True,
        {"alt": "sse"},
        id="gemini-streaming",
    ),
    pytest.param(
        "openai-responses-stream",
        Provider.OPENAI_RESPONSES,
        "/v1/responses",
        "gpt-4o",
        True,
        None,
        id="openai-responses-streaming",
    ),
    pytest.param(
        "bedrock",
        Provider.BEDROCK,
        "/model/amazon.titan-text-express-v1/converse",
        "amazon.titan-text-express-v1",
        False,
        None,
        id="bedrock",
    ),
]


@pytest.mark.flaky(reruns=3, reruns_delay=25)
@pytest.mark.parametrize("mock_provider,llm_provider,path,model,streaming,query", PROVIDERS)
def test_default_pointer_extracts_usage(
    client, mockserver_client, mock_provider, llm_provider, path, model, streaming, query
):
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
        query=query,
    )
    headers = {"x-mock-provider": mock_provider}

    requests_until_limit = math.ceil(LIMIT.limit / TOTAL_TOKENS)
    for i in range(requests_until_limit):
        response = client.post(path, json={"model": model}, headers=headers, params=query)
        assert (
            response.status_code == 200
        ), f"Expected 200 on request {i + 1}/{requests_until_limit} for {llm_provider}, got {response.status_code}"

    response = client.post(path, json={"model": model}, headers=headers, params=query)
    assert response.status_code == 429, (
        f"Expected 429 for {llm_provider} after {requests_until_limit} requests (default totalTokens "
        f"pointer should have extracted usage from the {llm_provider} response shape), got {response.status_code}"
    )
