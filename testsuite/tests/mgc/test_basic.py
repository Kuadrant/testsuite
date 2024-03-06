"""
This module contains the most basic happy path test for both DNSPolicy and TLSPolicy

Prerequisites:
* multi-cluster-gateways ns is created and set as openshift["project"]
* managedclustersetbinding is created in openshift["project"]
* gateway class "kuadrant-multi-cluster-gateway-instance-per-cluster" is created

"""

import pytest

pytestmark = [pytest.mark.mgc]


def test_gateway_readiness(gateway):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    assert gateway.is_ready()


def test_smoke(client):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by MGC
    """

    result = client.get("/get")
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200
