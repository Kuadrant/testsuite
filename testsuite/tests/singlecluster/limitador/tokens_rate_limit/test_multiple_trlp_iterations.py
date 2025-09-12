"""
Tests that a TokenRateLimitPolicy limit is enforced and resets as expected over multiple iterations
"""

from time import sleep
import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # TRLP only supports non-streaming currently
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
}


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for this test"""
    return None


@pytest.fixture(scope="module", params=["route", "gateway"])
def token_rate_limit(request, cluster, blame, module_label):
    """Overrides TRLP with a smaller limit"""
    target_ref = request.getfixturevalue(request.param)

    policy = TokenRateLimitPolicy.create_instance(
        cluster, blame(f"trlp-{request.param}"), target_ref, labels={"testRun": module_label}
    )

    policy.add_limit(name="limit", limits=[Limit(limit=10, window="10s")])
    return policy


def test_multiple_trlp_limit_iterations(client):
    """Ensures TRLP limit resets correctly over multiple iterations"""
    for i in range(10):
        total_tokens = 0
        limit = 20

        while total_tokens <= limit:
            response = client.post("/v1/chat/completions", json={**basic_request, "max_tokens": 10})
            if response.status_code == 429:
                break
            assert (
                response.status_code == 200
            ), f"Iteration {i+1}: Expected 200 before limit, got {response.status_code}"

            tokens_used = response.json()["usage"]["total_tokens"]
            assert tokens_used > 0, f"Got 0 tokens on iteration {i+1}"
            total_tokens += tokens_used

        response = client.post("/v1/chat/completions", json={**basic_request, "max_tokens": 5})
        assert (
            response.status_code == 429
        ), f"Iteration {i+1}: Expected 429 after {total_tokens} tokens, but got {response.status_code}"

        sleep(12)
        response = client.post("/v1/chat/completions", json={**basic_request, "max_tokens": 5})
        assert response.status_code == 200, f"Iteration {i+1}: Expected 200 after reset, but got {response.status_code}"
