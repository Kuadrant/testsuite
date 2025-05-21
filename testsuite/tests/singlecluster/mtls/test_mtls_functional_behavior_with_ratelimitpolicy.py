"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR (ratelimitpolicy)
"""

import time

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def authorization():
    """Disable AuthPolicy creation during these tests"""
    return None


def test_requests_succeed_when_mtls_disabled_rlp(kuadrant, client, rate_limit):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsLimitador") is False
    assert kuadrant.model.status.get("mtlsAuthorino") in (False, None)

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_requests_succeed_when_mtls_enabled_rlp(
    kuadrant, client, rate_limit, wait_for_mtls_status, reset_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="limitador")

    assert kuadrant.model.spec.mtls.enable is True
    assert kuadrant.model.status.get("mtlsLimitador") is True
    assert kuadrant.model.status.get("mtlsAuthorino") in (False, None)

    rate_limit.wait_for_ready()
    time.sleep(10)  # This is needed also as wait for ready is not enough

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_requests_still_succeed_after_mtls_disabled_again_rlp(
    kuadrant, client, rate_limit
):  # pylint: disable=unused-argument
    """Tests that requests succeed after disabling mTLS again"""
    kuadrant.refresh().model.spec.mtls = {"enable": False}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    kuadrant.wait_until(lambda obj: obj.model.status.mtls is False)

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.get("mtlsLimitador") is False
    assert kuadrant.model.status.get("mtlsAuthorino") in (False, None)

    rate_limit.wait_for_ready()

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
