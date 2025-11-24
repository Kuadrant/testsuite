"""
This module contains tests for scaling the gateway deployment by manually increasing the replicas in the deployment spec
"""

import time
import pytest

from testsuite.tests.singlecluster.gateway.scaling.conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


def test_scale_gateway(gateway, client, auth):
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    anon_auth_resp = client.get("/anything/auth")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/anything/limit", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("anything/limit", auth=auth).status_code == 429

    gateway.deployment.set_replicas(2)
    gateway.deployment.wait_for_ready()

    time.sleep(5)  # sleep in order to reset the rate limit policy time limit.

    anon_auth_resp = client.get("/anything/auth")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/anything/limit", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/anything/limit", auth=auth).status_code == 429
