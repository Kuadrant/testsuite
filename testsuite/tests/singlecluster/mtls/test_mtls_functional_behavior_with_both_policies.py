"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR (authpolicy & ratelimitpolicy)
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]


def test_requests_succeed_when_mtls_disabled(
    kuadrant, client, rate_limit, authorization, auth
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsAuthorino") is False
    assert kuadrant.model.status.get("mtlsLimitador") is False

    responses = client.get_many("/get", 2, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429


def test_requests_succeed_when_mtls_enabled_both(
    kuadrant, client, rate_limit, authorization, auth, wait_for_mtls_status, reset_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="limitador")
    wait_for_mtls_status(kuadrant, expected=True, component="authorino")

    assert kuadrant.model.spec.mtls.enable is True
    assert kuadrant.model.status.get("mtlsLimitador") is True
    assert kuadrant.model.status.get("mtlsAuthorino") is True

    rate_limit.wait_for_ready()
    authorization.wait_for_ready()

    responses = client.get_many("/get", 2, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429


def test_requests_still_succeed_after_mtls_disabled_again(
    kuadrant, client, rate_limit, authorization, auth, wait_for_mtls_status
):  # pylint: disable=unused-argument
    """Tests that requests succeed after disabling mTLS again"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=False, component="limitador")
    wait_for_mtls_status(kuadrant, expected=False, component="authorino")

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsAuthorino") is False
    assert kuadrant.model.status.get("mtlsLimitador") is False

    rate_limit.wait_for_ready()
    authorization.wait_for_ready()

    responses = client.get_many("/get", 2, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429
