"""Testing specific bug that happens when listener hostname in Gateway gets changed while DNSPolicy is applied."""

import pytest
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.utils import is_nxdomain, sleep_ttl

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def wildcard_domain(base_domain, blame):
    """
    For this test we want specific domain, not wildcard.
    This will be used in the first iteration of Gateway and HTTPRoute.
    """
    return f"{blame('dnsbug1')}.{base_domain}"


@pytest.fixture(scope="module")
def new_domain(base_domain, blame):
    """In the test the Gateway and HTTPRoute will change their hostnames to this one."""
    return f"{blame('dnsbug2')}.{base_domain}"


@pytest.fixture(scope="module")
def client(gateway, wildcard_domain):
    """Make client point to correct domain route domain."""
    return StaticHostname(wildcard_domain, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def client_new(gateway, new_domain):
    """Second client that will be created after Gateway gets updated pointing to new_domain."""

    def _client_new():
        return StaticHostname(new_domain, gateway.get_tls_cert).client()

    return _client_new


@pytest.fixture(scope="module")
def route(route, wildcard_domain):
    """So that route hostname matches the gateway hostname."""
    route.remove_all_hostnames()
    route.add_hostname(wildcard_domain)
    return route


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/794")
def test_change_hostname(client, client_new, auth, gateway, route, new_domain, wildcard_domain):
    """
    This test checks if after change of listener hostname in a Gateway while having DNSPolicy applied, that
    the old hostname gets deleted from DNS provider. After editing the hostname in HTTPRoute to the new value
    this test checks the reconciliation of such procedure.

    WARNING
        Running this test in unpatched Kuadrant will leave orphaned DNS records in DNS provider.
        If you want to delete them you need to do it manually. The DNS records will contain string 'dnsbug'
    """
    result = client.get("/get", auth=auth)
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200

    gateway.refresh().model.spec.listeners[0].hostname = new_domain
    gateway.apply()
    route.refresh().model.spec.hostnames[0] = new_domain
    route.apply()

    result = client_new().get("/get", auth=auth)
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200

    sleep_ttl(wildcard_domain)
    assert is_nxdomain(wildcard_domain)
