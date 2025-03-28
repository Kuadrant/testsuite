"""Testing specific bug that happens when listener hostname in Gateway gets changed while DNSPolicy is applied."""

from time import sleep
import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.utils import is_nxdomain

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]

DEFAULT_LISTENER_NAME = TLSGatewayListener.name


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/794")
def test_change_listener(custom_client, check_ok_https, gateway, route, second_domain, wildcard_domain):
    """
    This test checks if after change of listener hostname in a Gateway while having DNSPolicy applied, that
    the old hostname gets deleted from DNS provider. After editing the hostname in HTTPRoute to the new value
    this test checks the reconciliation of such procedure.
    """
    check_ok_https(wildcard_domain)
    wildcard_domain_ttl = gateway.get_listener_dns_ttl(DEFAULT_LISTENER_NAME)

    gateway.refresh().model.spec.listeners[0].hostname = second_domain
    gateway.apply()
    route.remove_hostname(wildcard_domain)
    route.add_hostname(second_domain)

    sleep(wildcard_domain_ttl)
    check_ok_https(second_domain)
    assert is_nxdomain(wildcard_domain)
    assert custom_client(wildcard_domain).get("/get").has_dns_error()
