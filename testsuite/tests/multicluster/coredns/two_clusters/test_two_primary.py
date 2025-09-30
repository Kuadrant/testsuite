"""Coredns setup with 2 primary clusters"""

import dns.resolver
import pytest

from testsuite.kubernetes.secret import Secret
from ..conftest import IP1, IP2

pytestmark = [pytest.mark.multicluster]


@pytest.fixture(scope="module")
def set_delegate_mode():
    """No delegation is required"""


@pytest.fixture(scope="module")
def kubeconfig_secrets(testconfig, cluster, cluster2, blame, module_label):
    """Creates Opaque secret containing kubeconfigs for both primary clusters on each other"""
    tools = cluster.change_project("tools")
    coredns_sa = tools.get_service_account("coredns")
    kubeconfig = coredns_sa.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools.api_url)

    tools2 = cluster2.change_project("tools")
    coredns_sa2 = tools2.get_service_account("coredns")
    kubeconfig2 = coredns_sa2.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools2.api_url)

    secrets = []
    for c, k in [(cluster, kubeconfig2), (cluster2, kubeconfig)]:
        secrets.append(
            Secret.create_instance(
                c.change_project(testconfig["service_protection"]["system_project"]),
                blame("kubecfg"),
                {"kubeconfig": k},
                secret_type="Opaque",
                labels={"app": module_label, "kuadrant.io/multicluster-kubeconfig": "true"},
            )
        )
    return secrets


def test_two_primary(testconfig):
    """IPs from both primary clusters should return in DNS A record set"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(f'ns1.{testconfig["dns"]["coredns_zone"]}')}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"
