"""Test for modification of default geolocation in DNSPolicy"""

from time import sleep

import pytest
import dns.resolver

pytestmark = [pytest.mark.multicluster]


def test_change_default_geo(hostname, gateway, gateway2, dns_policy, dns_policy2, dns_default_geo_server):
    """Test changing dns default geolocation and verify that changes are propagated"""
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [dns_default_geo_server]

    assert resolver.resolve(hostname.hostname)[0].address == gateway.external_ip().split(":")[0]

    dns_policy.refresh().model.spec.loadBalancing.defaultGeo = False
    res = dns_policy.apply()
    assert res.status() == 0, res.err()
    dns_policy.wait_for_ready()

    dns_policy2.refresh().model.spec.loadBalancing.defaultGeo = True
    res2 = dns_policy2.apply()
    assert res2.status() == 0, res2.err()
    dns_policy2.wait_for_ready()

    sleep(300)  # wait for DNS propagation on providers
    assert resolver.resolve(hostname.hostname)[0].address == gateway2.external_ip().split(":")[0]
