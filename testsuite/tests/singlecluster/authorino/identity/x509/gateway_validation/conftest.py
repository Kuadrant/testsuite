"""Conftest for gateway-level client certificate validation tests with frontend TLS validation"""

import pytest

from testsuite.gateway import TLSGatewayListener, Exposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.kubernetes.config_map import ConfigMap


@pytest.fixture(scope="module")
def exposer(request, testconfig, cluster) -> Exposer:
    """Exposer object instance with TLS passthrough"""
    exposer = testconfig["default_exposer"](cluster)
    exposer.passthrough = True  # Gateway needs to terminate TLS to validate client certificates
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def base_domain(exposer):
    """Returns preconfigured base domain"""
    return exposer.base_domain


@pytest.fixture(scope="module")
def wildcard_domain(base_domain):
    """Wildcard domain for the exposer"""
    return f"*.{base_domain}"


@pytest.fixture(scope="module")
def client_ca_config_map(request, cluster, blame, client_ca):
    """ConfigMap containing the trusted CA certificate for frontend TLS validation"""
    config_map = ConfigMap.create_instance(cluster, blame("client-ca"), data={"ca.crt": client_ca.certificate})
    request.addfinalizer(config_map.delete)
    config_map.commit()
    return config_map


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label, client_ca_config_map):
    """Gateway with TLS listener and frontend TLS client certificate validation"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, labels={"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=gateway_name))
    gw.set_frontend_tls_validation(
        [{"name": client_ca_config_map.name(), "kind": "ConfigMap", "group": ""}],
    )
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def server_ca(gateway, hostname):
    """Server-side TLS certificate from the gateway for verifying the TLS connection"""
    return gateway.get_tls_cert(hostname.hostname)


@pytest.fixture(scope="module")
def tls_policy(blame, gateway, module_label, cluster_issuer):
    """TLSPolicy"""
    return TLSPolicy.create_instance(
        gateway.cluster, blame("tls"), parent=gateway, issuer=cluster_issuer, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(request, tls_policy, authorization):
    """Commits TLSPolicy and AuthPolicy"""
    for component in [tls_policy, authorization]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
