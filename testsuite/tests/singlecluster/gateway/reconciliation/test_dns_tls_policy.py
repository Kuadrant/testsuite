"""Test that changes hostname of gateway and route and will check if DNS and TLS Policy still works"""

import pytest
from testsuite.gateway.gateway_api.hostname import StaticHostname

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module", autouse=True)
def commit(request, dns_policy, tls_policy):
    """Rewrites commit so it creates just dns and tls policy"""
    for component in [dns_policy, tls_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()


@pytest.fixture(scope="module")
def wildcard_domain(base_domain):
    """creates first custom wildcard domain"""
    return f"domain1.{base_domain}"


@pytest.fixture(scope="module")
def wildcard_domain2(base_domain):
    """creates second custom wildcard domain"""
    return f"domain2.{base_domain}"


@pytest.fixture(scope="module")
def client(gateway, wildcard_domain):
    """Make client point to correct domain route domain."""
    return StaticHostname(wildcard_domain, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def client_new(gateway, wildcard_domain2):
    """Second client that will be created after Gateway gets updated pointing to new_domain."""

    def _client_new():
        return StaticHostname(wildcard_domain2, gateway.get_tls_cert).client()

    return _client_new


@pytest.fixture(scope="module")
def route(route, wildcard_domain):
    """So that route hostname matches the gateway hostname."""
    route.remove_all_hostnames()
    route.add_hostname(wildcard_domain)
    return route


def test_create_gw(gateway, wildcard_domain2, client, client_new, route):
    """
    This test is supposed to test changing parentRef of a DNSPolicy/TLSPolicy from Gateway A
    with hostname A to Gateway B with hostname B
    """
    response = client.get("/get")
    assert not response.has_dns_error()
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    gateway.refresh().model.spec.listeners[0].hostname = wildcard_domain2
    gateway.apply()
    route.refresh().model.spec.hostnames[0] = wildcard_domain2
    route.apply()

    response = client_new().get("/get")
    assert not response.has_dns_error()
    assert not response.has_cert_verify_error()
    assert response.status_code == 200
