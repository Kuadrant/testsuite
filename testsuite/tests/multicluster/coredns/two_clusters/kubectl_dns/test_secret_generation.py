"""Test kubectl-dns add-cluster-secret command with basic coredns setup with 1 primary and 1 secondary clusters"""

import shutil

import dns.resolver
import pytest

from testsuite.cli.kubectl_dns import KubectlDNS
from testsuite.tests.multicluster.coredns.conftest import IP1, IP2

pytestmark = [pytest.mark.cli]


@pytest.fixture(scope="session")
def kubectl_dns(testconfig, skip_or_fail):
    """Return Kuadrantctl wrapper with merged kubeconfig"""
    binary_path = testconfig["kubectl-dns"]
    if not shutil.which(binary_path):
        skip_or_fail("kubectl-dns binary not found")
    return KubectlDNS(binary_path)


@pytest.fixture(scope="module")
def kubeconfig_secrets(request, system_project, cluster, cluster2, kubectl_dns, blame):
    """Run add-cluster-secret command on merged kubeconfig to generate kubeconfig secret for the secondary cluster"""
    secret_name = blame("kubecfg")
    request.addfinalizer(
        lambda: cluster.do_action("delete", "secret", secret_name, "-n", system_project.project, "--ignore-not-found")
    )

    merged_kubeconfig = cluster.create_merged_kubeconfig(cluster2)
    result = kubectl_dns.run(
        "add-cluster-secret",
        "--name",
        secret_name,
        "--context",
        cluster2.current_context_name,
        "--namespace",
        system_project.project,
        "--service-account",
        "coredns",
        env={"KUBECONFIG": merged_kubeconfig},
    )
    assert result.returncode == 0, f"kubectl-dns couldn't generate kubeconfig secret: {result.stderr}"
    return []


def test_kubectl_dns_secret_generation(hostname):
    """IPs from both, primary and secondary, clusters should return in DNS A record set"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"
