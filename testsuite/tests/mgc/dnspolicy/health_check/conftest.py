"""Conftest for DNSPolicy health checks"""
import time
import pytest

from testsuite.gateway import Hostname
from testsuite.gateway.gateway_api.gateway import MGCGateway


@pytest.fixture(scope="module")
def name(blame):
    """Hostname that will be added to HTTPRoute"""
    return blame("hostname")


@pytest.fixture(scope="module")
def hostname(gateway, exposer, name) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(name, gateway)
    return hostname


@pytest.fixture(scope="module")
def hub_gateway(request, hub_openshift, blame, name, base_domain, module_label):
    """
    Creates and returns configured and ready upstream Gateway with FQDN hostname
    Health checks available only with Fully Qualified Domain Names in gateway (no wildcards are allowed)
    """
    hub_gateway = MGCGateway.create_instance(
        openshift=hub_openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        # This relies on exact naming scheme in DNSPolicyExposer, workaround for circular dependency
        hostname=f"{name}.{base_domain}",
        tls=False,
        placement="http-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(hub_gateway.delete)
    hub_gateway.commit()

    return hub_gateway


@pytest.fixture(scope="module")
def dns_policy(dns_policy, health_check):
    """Add health check to DNSPolicy"""
    dns_policy.set_health_check(health_check)
    return dns_policy


@pytest.fixture(scope="module")
def dns_health_probe(dns_policy, route):  # pylint: disable=unused-argument
    """Wait for health check to start monitoring endpoint and return according DNSHealthCheckProbe object"""
    time.sleep(10)
    return dns_policy.get_dns_health_probe()
