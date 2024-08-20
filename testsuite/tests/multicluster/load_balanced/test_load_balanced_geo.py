"""Test load-balancing based on geolocation"""

import pytest
import dns.name
import dns.resolver

pytestmark = [pytest.mark.multicluster]


@pytest.fixture(scope="module")
def gateway2(gateway2, dns_server2):
    """Overwrite second gateway to have a different geocode"""
    gateway2.label({"kuadrant.io/lb-attribute-geo-code": dns_server2["geo_code"]})
    return gateway2


def test_load_balanced_geo(client, hostname, gateway, gateway2, dns_server, dns_server2):
    """
    - Verify that request to the hostname is successful
    - Verify that DNS resolution through nameservers from different regions returns according IPs
    """
    result = client.get("/get")
    assert not result.has_dns_error(), result.error
    assert not result.has_cert_verify_error(), result.error
    assert result.status_code == 200

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [dns_server["address"]]
    assert resolver.resolve(hostname.hostname)[0].address == gateway.external_ip().split(":")[0]

    resolver.nameservers = [dns_server2["address"]]
    assert resolver.resolve(hostname.hostname)[0].address == gateway2.external_ip().split(":")[0]
