"""
Test that DNSPolicy created with delegate: false on secondary cluster
won't propagate its external DNS provider IP to the authoritative DNS record
"""

import dns.resolver
import pytest

from testsuite.gateway import GatewayListener
from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from ..conftest import IP1, IP2

pytestmark = [pytest.mark.coredns_one_primary]


@pytest.fixture(scope="module")
def kubeconfig_secrets(testconfig, cluster, cluster2, blame, module_label):
    """Creates Opaque secrets containing kubeconfigs for the secondary cluster2 on the primary cluster"""
    tools2 = cluster2.change_project("tools")
    coredns_sa2 = tools2.get_service_account("coredns")
    kubeconfig2 = coredns_sa2.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools2.api_url)

    return [
        Secret.create_instance(
            cluster.change_project(testconfig["service_protection"]["system_project"]),
            blame("kubecfg"),
            {"kubeconfig": kubeconfig2},
            secret_type="Opaque",
            labels={"app": module_label, "kuadrant.io/multicluster-kubeconfig": "true"},
        )
    ]


@pytest.fixture(scope="module")
def exposer2(request, cluster2):
    """Expose using DNSPolicy for the not delegated DNSPolicy"""
    exposer = DNSPolicyExposer(cluster2)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def hostname2(gateway2, exposer2, blame):
    """Exposed hostname for the not delegated DNSPolicy"""
    return exposer2.expose_hostname(blame("hostname"), gateway2)


@pytest.fixture(scope="module")
def gateway2(cluster2, blame, label, exposer2):
    """Gateway object for the not delegated DNSPolicy"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster2, name, {"app": label})
    gw.add_listener(GatewayListener(hostname=f"*.{exposer2.base_domain}"))
    return gw


@pytest.fixture(scope="module")
def route2(request, gateway2, blame, hostname2, backends, module_label):
    """Route object for the not delegated DNSPolicy"""
    route = HTTPRoute.create_instance(gateway2.cluster, blame("route"), gateway2, {"app": module_label})
    route.add_hostname(hostname2.hostname)
    route.add_backend(backends[1])
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_provider_secret, module_label):
    """DNSPolicy for the second cluster"""
    return DNSPolicy.create_instance(
        cluster2, blame("dns"), gateway2, dns_provider_secret, delegate=False, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(
    request, coredns_secrets, kubeconfig_secrets, dnsrecord1, dnsrecord2, route2, gateway2, dns_policy2
):  # pylint: disable=unused-argument
    """Commits all components required for the test and adds finalizers to delete them on cleanup"""
    for component in [*kubeconfig_secrets, dnsrecord1, dnsrecord2, gateway2, dns_policy2]:
        request.addfinalizer(component.delete)
        component.commit()
    for component in [dnsrecord1, dnsrecord2, gateway2, dns_policy2]:
        component.wait_for_ready()


def test_delegate_false(gateway2, hostname, hostname2):
    """
    Test that DNSPolicy created with delegate: false on secondary cluster
    won't propagate its external DNS provider IP to the authoritative DNS record
    """
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"

    assert (
        dns.resolver.resolve(hostname2.hostname)[0].address == gateway2.external_ip().split(":")[0]
    ), "external DNS provider IP SHOULD be in a AWS DNS record"
    assert (
        gateway2.external_ip().split(":")[0] not in dns_ips
    ), "external DNS provider IP SHOULD NOT be in a authoritative DNS record"
