"""Conftest for DNSPolicy health checks"""
import time
import pytest

from testsuite.openshift.objects.gateway_api.gateway import MGCGateway


@pytest.fixture(scope="module")
def upstream_gateway(request, openshift, blame, module_label, initial_host):
    """
    Creates and returns configured and ready upstream Gateway with FQDN hostname
    Health checks available only with Fully Qualified Domain Names in gateway (no wildcards are allowed)
    """
    upstream_gateway = MGCGateway.create_instance(
        openshift=openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=initial_host,
        tls=False,
        placement="http-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(upstream_gateway.delete)
    upstream_gateway.commit()

    return upstream_gateway


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
