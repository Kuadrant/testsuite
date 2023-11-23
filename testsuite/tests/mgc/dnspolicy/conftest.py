"""Conftest for DNSPolicy tests"""
import pytest

from testsuite.gateway.gateway_api.gateway import MGCGateway


@pytest.fixture(scope="module")
def hub_gateway(request, hub_openshift, blame, base_domain, module_label):
    """Creates and returns configured and ready upstream Gateway with disabled tls"""
    hub_gateway = MGCGateway.create_instance(
        openshift=hub_openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=f"*.{base_domain}",
        tls=False,
        placement="http-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(hub_gateway.delete)
    hub_gateway.commit()

    return hub_gateway


@pytest.fixture(scope="module")
def tls_policy():
    """Don't need TLSPolicy in the DNSPolicy only tests"""
    return None
