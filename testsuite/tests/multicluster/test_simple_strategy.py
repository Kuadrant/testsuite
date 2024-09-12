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
    Tests DNS/TLS across multiple clusters
    - Checks that all Gateways will get ready
    - Checks that request to the hostname works
    - Checks DNS records values
    """
    result = client.get("/get")
    assert not result.has_dns_error(), result.error
    assert not result.has_cert_verify_error(), result.error
    assert result.status_code == 200

    dns_ip1 = dns.resolver.resolve(hostname.hostname)[0].address
    dns_ip2 = dns.resolver.resolve(hostname.hostname)[0].address
    assert dns_ip1 != dns_ip2, "Simple routing strategy should return IPs in a round-robin fashion"

    gateway_ips = {gateway.external_ip().split(":")[0], gateway2.external_ip().split(":")[0]}
    dns_ips = {dns_ip1, dns_ip2}
    assert gateway_ips == dns_ips, f"Expected and actual IPs mismatch, expected {gateway_ips}, got {dns_ips}"
