"""
Conftest for Gateway listeners tests.
The main change consists of replacing the default wildcard domain for an exact one.
"""

import pytest

from testsuite.gateway.gateway_api.hostname import StaticHostname


@pytest.fixture(scope="module")
def wildcard_domain(base_domain, blame):
    """
    For these tests we want specific default domain, not wildcard.
    """
    return f'{blame("prefix1")}.{base_domain}'


@pytest.fixture(scope="module")
def second_domain(base_domain, blame):
    """Second domain string, not used in any object yet. To be assigned inside test."""
    return f'{blame("prefix2")}.{base_domain}'


@pytest.fixture(scope="module")
def custom_client(gateway):
    """
    While changing TLS listeners the TLS certificate changes so a new client needs to be generated
    to fetch newest tls cert from cluster.
    """

    def _client_new(hostname: str):
        return StaticHostname(hostname, gateway.get_tls_cert).client()

    return _client_new


@pytest.fixture(scope="module")
def check_ok_https(custom_client, auth):
    """
    Assert that HTTPS connection to domain works and returns 200. Authorization is used.
    Assert that no DNS and TLS errors happened.
    """

    def _check_ok_https(domain: str):
        response = custom_client(domain).get("/get", auth=auth)
        assert not response.has_dns_error()
        assert not response.has_cert_verify_error()
        assert response.status_code == 200

    return _check_ok_https


@pytest.fixture(scope="module")
def route(route, wildcard_domain):
    """Ensure that route hostname matches the gateway hostname."""
    route.remove_all_hostnames()
    route.add_hostname(wildcard_domain)
    return route
