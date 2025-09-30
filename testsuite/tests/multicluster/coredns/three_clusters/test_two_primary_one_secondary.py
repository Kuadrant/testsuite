"""Coredns setup with 2 primary and 1 secondary clusters"""

import dns.resolver
import pytest

from testsuite.kubernetes.secret import Secret
from ..conftest import IP1, IP2
from .conftest import IP3

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def kubeconfig_secrets(testconfig, blame, module_label, cluster, cluster2, cluster3):  # pylint: disable=too-many-locals
    """Creates Opaque secrets containing kubeconfig for primaries, and secondary cluster3 on the both primaries"""
    tools = cluster.change_project("tools")
    coredns_sa = tools.get_service_account("coredns")
    kubeconfig = coredns_sa.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools.api_url)

    tools2 = cluster2.change_project("tools")
    coredns_sa2 = tools2.get_service_account("coredns")
    kubeconfig2 = coredns_sa2.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools2.api_url)

    tools3 = cluster3.change_project("tools")
    coredns_sa3 = tools3.get_service_account("coredns")
    kubeconfig3 = coredns_sa3.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools3.api_url)

    kubeconfig_secrets = []
    for c, k in [(cluster, kubeconfig2), (cluster, kubeconfig3), (cluster2, kubeconfig), (cluster2, kubeconfig3)]:
        kubeconfig_secrets.append(
            Secret.create_instance(
                c.change_project(testconfig["service_protection"]["system_project"]),
                blame("kubecfg"),
                {"kubeconfig": k},
                secret_type="Opaque",
                labels={"app": module_label, "kuadrant.io/multicluster-kubeconfig": "true"},
            )
        )
    return kubeconfig_secrets


def test_two_primary_one_secondary(testconfig):
    """IPs from 2 primary and 1 secondary clusters should return in DNS A record set"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(f'ns1.{testconfig["dns"]["coredns_zone"]}')}
    assert {IP1, IP2, IP3} == dns_ips, "CoreDNS should have returned all 3 IP addresses in A record set"
