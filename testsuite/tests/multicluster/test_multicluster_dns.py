"""Tests DNS/TLSPolicy across multiple clusters"""

import dns.resolver


def test_gateway_readiness(gateways):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    for client, gateway in gateways.items():
        assert gateway.is_ready(), f"Gateway {gateway.name()} on a server {client.api_url} did not get ready"


def test_multicluster_dns(client, hostname, gateways):
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

    ips = {gateway.external_ip().split(":")[0] for gateway in gateways.values()}
    dns_ips = set(())
    for _ in range(len(ips)):
        answer = dns.resolver.resolve(hostname.hostname)[0]
        assert answer.address in ips, f"Got {answer.address} that is not expected in {ips}"
        dns_ips.add(answer.address)
    assert ips == dns_ips, f"Expected IPs and actual IP mismatch, got {ips}, expected {ips}"
