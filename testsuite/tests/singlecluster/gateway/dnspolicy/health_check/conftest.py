"""Conftest for DNSPolicy health checks"""

import pytest

from testsuite.gateway import Hostname, TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway


@pytest.fixture(scope="module")
def subdomain(blame):
    """Subdomain name that will be added to HTTPRoute"""
    return blame("hostname")


@pytest.fixture(scope="module")
def hostname(gateway, exposer, subdomain) -> Hostname:
    """Exposed Hostname object"""
    return exposer.expose_hostname(subdomain, gateway)


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, base_domain, module_label, subdomain):
    """Returns ready gateway"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(
        cluster,
        gateway_name,
        {"app": module_label},
    )
    gw.add_listener(TLSGatewayListener(hostname=f"{subdomain}.{base_domain}", gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_policy(dns_policy, health_check):
    """Add health check to DNSPolicy"""
    dns_policy.set_health_check(health_check)
    return dns_policy


@pytest.fixture(scope="module")
def dns_health_probe(dns_policy):
    """Return DNSHealthCheckProbe object for created DNSPolicy"""
    dns_health_probe = dns_policy.get_dns_health_probe()
    dns_health_probe.wait_for_ready()
    return dns_health_probe


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, tls_policy, dns_policy):  # pylint: disable=unused-argument
    """Commits dnspolicy"""
    for component in [tls_policy, dns_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
