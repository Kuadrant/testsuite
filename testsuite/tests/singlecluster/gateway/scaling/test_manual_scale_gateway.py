"""
This module contains tests for scaling the gateway deployment by manually increasing the replicas in the deployment spec
"""

import time

import pytest

from testsuite.kuadrant.policy import CelExpression
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def rate_limit(blame, gateway, module_label, cluster):
    """Add limit to the policy"""
    policy = RateLimitPolicy.create_instance(cluster, blame("rlp"), gateway, labels={"app": module_label})
    policy.add_limit("basic", [Limit(5, "60s")], counters=[CelExpression("auth.identity.user")])
    return policy


# pylint: disable=unused-argument
def test_scale_gateway(gateway, client, auth, authorization):
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429

    gateway.deployment.set_replicas(2)
    gateway.deployment.wait_for_ready()

    time.sleep(60)

    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
