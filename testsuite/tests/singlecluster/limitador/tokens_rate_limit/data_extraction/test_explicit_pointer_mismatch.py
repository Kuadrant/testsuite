"""
Verifies that an explicit `dataExtraction.response.totalTokens` pointer list on TokenRateLimitPolicy
replaces the built-in default pointer list (RFC 0024), rather than supplementing it: a response
shape that a *default* pointer would normally resolve must stop counting once that pointer is
dropped from the explicit list, while a response matching the explicit pointer still counts.
"""

import math

import pytest
from mockserver.llm import Completion, Provider, Usage

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

from .conftest import LIMIT

pytestmark = [pytest.mark.limitador]

INPUT_TOKENS = 5
OUTPUT_TOKENS = 5
TOTAL_TOKENS = INPUT_TOKENS + OUTPUT_TOKENS
NUM_SUCCESSFUL = math.ceil(LIMIT.limit / TOTAL_TOKENS)  # requests needed to exhaust LIMIT at TOTAL_TOKENS each

# One isolated counter bucket per case, matched via the x-mock-provider request header.
MOCK_PROVIDERS = ("openai-match", "gemini-mismatch")

# Policy only configures OpenAI's pointer; Gemini's shape is covered by a *default* pointer that
# must no longer apply once an explicit list is set.
CASES = [
    pytest.param(
        "openai-match", Provider.OPENAI, "/v1/chat/completions", "gpt-4o", True, id="matches-explicit-pointer"
    ),
    pytest.param(
        "gemini-mismatch",
        Provider.GEMINI,
        "/v1beta/models/gemini-2.0-flash:generateContent",
        "gemini-2.0-flash",
        False,
        id="mismatches-explicit-pointer",
    ),
]


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """TokenRateLimitPolicy with an explicit totalTokens pointer covering only OpenAI's response
    shape, to verify explicit dataExtraction replaces (rather than supplements) the built-in defaults"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.set_data_extraction(["/usage/total_tokens"])
    for mock_provider in MOCK_PROVIDERS:
        policy.add_limit(
            name=f"{mock_provider}-limit",
            limits=[LIMIT],
            when=[CelPredicate(predicate=f'request.headers["x-mock-provider"] == "{mock_provider}"')],
        )
    return policy


@pytest.mark.flaky(reruns=3, reruns_delay=25)
@pytest.mark.parametrize("mock_provider,llm_provider,path,model,expect_limited", CASES)
def test_explicit_pointer_replaces_defaults(
    client, mockserver_client, mock_provider, llm_provider, path, model, expect_limited
):
    """An explicit totalTokens pointer list must replace the built-in defaults, not supplement them"""
    mockserver_client.create_llm_response_expectation(
        f"trlp-{mock_provider}",
        path,
        llm_provider,
        completion=Completion(
            text="mocked response",
            usage=Usage(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
        ),
        model=model,
    )
    headers = {"x-mock-provider": mock_provider}

    responses = [client.post(path, json={"model": model}, headers=headers) for _ in range(NUM_SUCCESSFUL + 1)]
    statuses = [response.status_code for response in responses]

    expected = [200] * NUM_SUCCESSFUL + [429] if expect_limited else [200] * (NUM_SUCCESSFUL + 1)
    assert statuses == expected, (
        f"Explicit totalTokens pointer (OpenAI-only) {'should' if expect_limited else 'should not'} "
        f"have extracted usage from the {llm_provider} response shape, got statuses {statuses}"
    )
