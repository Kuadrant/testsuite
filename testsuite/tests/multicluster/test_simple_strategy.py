"""Tests DNS/TLSPolicy across multiple clusters"""

import dns.resolver
import pytest

pytestmark = [pytest.mark.multicluster]


def test_gateway_readiness(gateway, gateway2):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    assert gateway.is_ready(), "Gateway on the first cluster did not get ready in time"
    assert gateway2.is_ready(), "Gateway on the second cluster did not get ready in time"


def test_simple_strategy(client, hostname, gateway, gateway2):
    """
    Test simple load-balancing strategy across multiple clusters
    - Checks that request to the hostname works
    - Checks that DNS resolution return IPs in a round-robin fashion
    """
    result = client.get("/get")
    assert not result.has_dns_error(), result.error
    assert not result.has_cert_verify_error(), result.error
    assert result.status_code == 200

    gw1_ip, gw2_ip = gateway.external_ip().split(":")[0], gateway2.external_ip().split(":")[0]
    assert gw1_ip != gw2_ip

    gw1_ip_resolved = dns.resolver.resolve(hostname.hostname)[0].address
    gw2_ip_resolved = dns.resolver.resolve(hostname.hostname)[0].address
    assert gw1_ip_resolved != gw2_ip_resolved, "Simple routing strategy should return IPs in a round-robin fashion"
    assert {gw1_ip_resolved, gw2_ip_resolved} == {gw1_ip, gw2_ip}

    for i in range(10):
        assert (
            dns.resolver.resolve(hostname.hostname)[0].address == gw1_ip_resolved
        ), f"Simple routing strategy should return IPs in a round-robin fashion (iteration {i + 1})"
        assert (
            dns.resolver.resolve(hostname.hostname)[0].address == gw2_ip_resolved
        ), f"Simple routing strategy should return IPs in a round-robin fashion (iteration {i + 1})"
