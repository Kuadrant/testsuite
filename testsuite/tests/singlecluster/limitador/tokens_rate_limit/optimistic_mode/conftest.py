"""Conftest for the Optimistic mode opt-out tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

LIMIT = Limit(limit=200, window="20s")


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module", autouse=True)
def optimistic_mode(request, kuadrant):
    """Switches the Kuadrant CR to Optimistic (Check/Report) mode for the duration of this module"""
    if (kuadrant.model.spec.get("tokenRateLimiting") or {}).get("mode") == "Optimistic":
        # Leftover dirty state from an earlier run: reset to the default first, so the
        # switch to Optimistic below is a genuine transition rather than a no-op.
        kuadrant.reset_token_rate_limiting_mode()
        kuadrant.wait_for_ready()

    def _reset_and_settle():
        kuadrant.reset_token_rate_limiting_mode()
        kuadrant.wait_for_ready()

    request.addfinalizer(_reset_and_settle)
    kuadrant.set_token_rate_limiting_mode("Optimistic")
    kuadrant.wait_for_ready()


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Creates a plain TRLP; reservation config is irrelevant while the cluster is in Optimistic mode"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit(name="limit", limits=[LIMIT])
    return policy
