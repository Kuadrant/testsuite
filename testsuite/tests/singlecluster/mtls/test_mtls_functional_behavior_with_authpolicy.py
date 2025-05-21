"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR (authpolicy)
"""

import time

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    return None


def test_requests_succeed_when_mtls_disabled_auth_policy(
    kuadrant, client, authorization, auth
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsAuthorino") is False
    assert kuadrant.model.status.get("mtlsLimitador") in (False, None)

    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_requests_succeed_when_mtls_enabled_auth_policy(
    kuadrant, client, authorization, auth, wait_for_mtls_status, reset_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="authorino")

    assert kuadrant.model.spec.mtls.enable is True
    assert kuadrant.model.status.get("mtlsAuthorino") is True
    assert kuadrant.model.status.get("mtlsLimitador") in (False, None)

    authorization.wait_for_ready()
    time.sleep(10)  # This is needed also as wait for ready is not enough

    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_requests_still_succeed_after_mtls_disabled_again_auth_policy(
    kuadrant, client, authorization, auth, wait_for_mtls_status
):  # pylint: disable=unused-argument
    """Tests that requests succeed after disabling mTLS again"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=False, component="authorino")

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsAuthorino") is False
    assert kuadrant.model.status.get("mtlsLimitador") in (False, None)

    response = client.get("/get", auth=auth)
    assert response.status_code == 200
