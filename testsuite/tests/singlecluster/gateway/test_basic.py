"""
This module contains the most basic happy path test for both DNSPolicy and TLSPolicy
"""

import pytest

pytestmark = [pytest.mark.dnspolicy, pytest.mark.tlspolicy, pytest.mark.smoke]


def test_gateway_readiness(gateway):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    assert gateway.is_ready()


def test_gateway_basic_dns_tls(client, auth):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by Kuadrant
    """

    result = client.get("/get", auth=auth)
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200
