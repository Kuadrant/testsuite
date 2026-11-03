"""Conftest for the Anthropic custom dataExtraction pointer test.

Anthropic's Messages API has no native total-tokens field (only usage.input_tokens/output_tokens),
so it isn't in TokenRateLimitPolicy's built-in default pointer list. Per RFC 0024, an explicit
dataExtraction.response.totalTokens can point at /usage/output_tokens as a documented, lossy
workaround (input tokens are omitted entirely, so this under-counts real usage).
"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

LIMIT = Limit(limit=25, window="20s")


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """TokenRateLimitPolicy with an explicit totalTokens pointer covering Anthropic's usage shape"""
    policy = TokenRateLimitPolicy.create_instance(
        cluster, blame("trlp-anthropic"), route, labels={"testRun": module_label}
    )
    policy.set_data_extraction(["/usage/output_tokens"])
    policy.add_limit(name="limit", limits=[LIMIT])
    return policy
