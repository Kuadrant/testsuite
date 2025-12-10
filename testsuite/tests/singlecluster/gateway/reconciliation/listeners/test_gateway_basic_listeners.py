"""
Test case:
- Add new listener and add it to HTTPRoute and test both work
- Remove the new listener and remove it from HTTPRoute and test removed one is not working
"""

from time import sleep
import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.utils import is_nxdomain


pytestmark = [pytest.mark.dnspolicy, pytest.mark.tlspolicy]

LISTENER_NAME = "api-second"


def test_listeners(custom_client, check_ok_https, gateway, route, wildcard_domain, second_domain):
    """
    This test checks reconciliation of dns/tls policy on addition and removal of listeners in gateway and HTTPRoute.
    """

    # Check the default domain works and second domain does not exist yet
    check_ok_https(wildcard_domain)
    assert is_nxdomain(second_domain)
    assert custom_client(second_domain).get("/get").has_dns_error()

    # Add second domain to gateway and route
    gateway.add_listener(TLSGatewayListener(hostname=second_domain, gateway_name=gateway.name(), name=LISTENER_NAME))
    route.add_hostname(second_domain)

    # Check both domains work
    for domain in [wildcard_domain, second_domain]:
        check_ok_https(domain)

    # Remove second domain, store TTL value of to be removed DNS record
    second_domain_ttl = gateway.get_listener_dns_ttl(LISTENER_NAME)
    route.remove_hostname(second_domain)
    gateway.remove_listener(LISTENER_NAME)

    # Check the default domain still works and second domain does not exist anymore
    sleep(second_domain_ttl)
    check_ok_https(wildcard_domain)
    assert is_nxdomain(second_domain)
    assert custom_client(second_domain).get("/get").has_dns_error()
