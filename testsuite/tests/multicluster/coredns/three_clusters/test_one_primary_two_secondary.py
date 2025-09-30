"""Coredns setup with 1 primary and 2 secondary clusters"""

import dns.resolver
import pytest

from testsuite.kubernetes.secret import Secret
from ..conftest import IP1, IP2
from .conftest import IP3

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def set_delegate_mode(request, set_delegate_mode, cluster2, testconfig):  # pylint: disable=unused-argument
    """Configures secondary cluster by patching dns-operator-controller-env configmap with DELEGATION_ROLE: secondary"""
    system_project = cluster2.change_project(testconfig["service_protection"]["system_project"])

    # add finalizer to remove the DELEGATION_ROLE patch and restart the controller, ORDER MATTERS
    dns_operator_controller = system_project.get_deployment("dns-operator-controller-manager")
    request.addfinalizer(dns_operator_controller.restart)
    remove_patch = '{"data":{"DELEGATION_ROLE":null}}'
    request.addfinalizer(
        lambda: system_project.do_action(
            "patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", remove_patch
        )
    )

    # Patch the configmap to add/update DELEGATION_ROLE: secondary
    add_patch = '{"data":{"DELEGATION_ROLE":"secondary"}}'
    system_project.do_action("patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", add_patch)

    dns_operator_controller.restart()


@pytest.fixture(scope="module")
def kubeconfig_secrets(testconfig, cluster, cluster2, cluster3, blame, module_label):
    """Creates Opaque secrets containing kubeconfigs for secondaries cluster2 and cluster3, on the primary cluster"""
    tools2 = cluster2.change_project("tools")
    coredns_sa2 = tools2.get_service_account("coredns")
    kubeconfig2 = coredns_sa2.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools2.api_url)

    tools3 = cluster3.change_project("tools")
    coredns_sa3 = tools3.get_service_account("coredns")
    kubeconfig3 = coredns_sa3.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools3.api_url)

    secrets = []
    for k in [kubeconfig2, kubeconfig3]:
        secrets.append(
            Secret.create_instance(
                cluster.change_project(testconfig["service_protection"]["system_project"]),
                blame("kubecfg"),
                {"kubeconfig": k},
                secret_type="Opaque",
                labels={"app": module_label, "kuadrant.io/multicluster-kubeconfig": "true"},
            )
        )
    return secrets


def test_one_primary_two_secondary(testconfig):
    """IPs from 1 primary and 2 secondary clusters should return in DNS A record set"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(f'ns1.{testconfig["dns"]["coredns_zone"]}')}
    assert {IP1, IP2, IP3} == dns_ips, "CoreDNS should have returned all 3 IP addresses in A record set"
