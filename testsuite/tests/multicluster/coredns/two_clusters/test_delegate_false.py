"""
Test that DNSPolicy created with delegate: false on secondary cluster
won't propagate its external DNS provider IP to the authoritative DNS record
"""

import dns.resolver
import pytest

from testsuite.gateway import GatewayListener
from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from ..conftest import IP1, IP2

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive]


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
def gateway2(cluster2, blame, label, wildcard_domain):
    """Overriding Gateway with not tls listener for this test"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster2, name, {"app": label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    return gw


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_provider_secret, module_label):
    """DNSPolicy for the second cluster"""
    return DNSPolicy.create_instance(
        cluster2, blame("dns"), gateway2, dns_provider_secret, delegate=False, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(
    request, coredns_secrets, kubeconfig_secrets, dnsrecord1, dnsrecord2, routes, gateway2, dns_policy2
):  # pylint: disable=unused-argument
    """Commits all components required for the test and adds finalizers to delete them on cleanup"""
    for component in [*kubeconfig_secrets, dnsrecord1, dnsrecord2, gateway2, dns_policy2]:
        request.addfinalizer(component.delete)
        component.commit()
    for component in [dnsrecord1, dnsrecord2, gateway2, dns_policy2]:
        component.wait_for_ready()


def test_delegate_false(testconfig, gateway2, hostname):
    """
    Test that DNSPolicy created with delegate: false on secondary cluster
    won't propagate its external DNS provider IP to the authoritative DNS record
    """
    dns_ips = {ip.address for ip in dns.resolver.resolve(f'ns1.{testconfig["dns"]["coredns_zone"]}')}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"

    assert (
        dns.resolver.resolve(hostname.hostname)[0].address == gateway2.external_ip().split(":")[0]
    ), "external DNS provider IP SHOULD be in a AWS DNS record"
    assert (
        gateway2.external_ip().split(":")[0] not in dns_ips
    ), "external DNS provider IP SHOULD NOT be in a authoritative DNS record"
