"""Conftest for mTLS tests"""

import time
import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def authorization():
    """Disable AuthPolicy creation during these tests"""
    return None


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(2, "10s")])
    return policy


def wait_for_mtls_status(kuadrant, expected: bool):
    """Wait until Kuadrant CR status.mtls matches the expected value"""
    for _ in range(10):
        kuadrant.refresh()
        if kuadrant.model.status.get("mtls") == expected:
            return
        time.sleep(2)

    raise TimeoutError("mTLS status did not reach expected value")
