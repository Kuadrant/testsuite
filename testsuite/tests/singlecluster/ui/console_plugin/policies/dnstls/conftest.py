"""Conftest for DNS and TLS Policy UI tests"""

import pytest

from testsuite.gateway import Exposer, TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, dns_wildcard_domain, module_label):
    """Override gateway to use TLS listener (required for DNS/TLS policies)"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=dns_wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_exposer(request, cluster) -> Exposer:
    """DNSPolicyExposer for DNS/TLS tests"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def dns_base_domain(dns_exposer):
    """DNS base domain for DNS/TLS tests"""
    return dns_exposer.base_domain


@pytest.fixture(scope="module")
def dns_wildcard_domain(dns_base_domain):
    """DNS wildcard domain for DNS/TLS tests"""
    return f"*.{dns_base_domain}"


@pytest.fixture(scope="module")
def hostname(gateway, dns_exposer, domain_name):
    """Override to use dns_exposer instead of session exposer"""
    return dns_exposer.expose_hostname(domain_name, gateway)


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label, dns_provider_secret):
    """DNSPolicy required for TLS policy to work"""
    policy = DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, gateway, module_label, cluster_issuer):
    """TLSPolicy to create TLS secret, required for client to work"""
    policy = TLSPolicy.create_instance(
        gateway.cluster,
        blame("tls"),
        parent=gateway,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, dns_policy, tls_policy):
    """Commit DNS and TLS policies"""
    for component in [dns_policy, tls_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()
