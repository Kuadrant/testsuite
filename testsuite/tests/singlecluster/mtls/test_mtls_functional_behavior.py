"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR
"""

import time
import pytest

from testsuite.tests.singlecluster.mtls.conftest import wait_for_mtls_status

pytestmark = [pytest.mark.kuadrant_only]


def test_requests_succeed_when_mtls_disabled(kuadrant, client, rate_limit):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    kuadrant.refresh()
    kuadrant.model.spec.mtls.enable = False
    kuadrant.apply()

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.mtls is False

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_requests_succeed_when_mtls_enabled(kuadrant, client, rate_limit):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    kuadrant.refresh()
    kuadrant.model.spec.mtls.enable = True
    kuadrant.apply()
    wait_for_mtls_status(kuadrant, expected=True)

    assert kuadrant.model.spec.mtls.enable is True
    assert kuadrant.model.status.mtls is True

    time.sleep(15)  # Delay to ensure system finishes applying mTLS changes before sending requests

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_requests_still_succeed_after_mtls_disabled_again(
    kuadrant, client, rate_limit
):  # pylint: disable=unused-argument
    """Tests that requests succeed after disabling mTLS again"""
    kuadrant.refresh()
    kuadrant.model.spec.mtls.enable = False
    kuadrant.apply()
    wait_for_mtls_status(kuadrant, expected=False)

    assert kuadrant.model.spec.mtls.enable is False
    assert kuadrant.model.status.mtls is False

    time.sleep(15)  # Delay to ensure system finishes applying mTLS changes before sending requests

    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
