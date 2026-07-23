"""Test kubectl-dns add-cluster-secret command with basic coredns setup with 1 primary and 1 secondary clusters"""

import dns.resolver
import pytest

from testsuite.tests.multicluster.coredns.conftest import IP1, IP2

pytestmark = [pytest.mark.cli]


@pytest.fixture(scope="module")
def kubeconfig_secrets(request, system_project, cluster, cluster2, kubectl_dns, blame):
    """Run add-cluster-secret command on merged kubeconfig to generate kubeconfig secret for the secondary cluster"""
    secret_name = blame("kubecfg")
    request.addfinalizer(
        lambda: cluster.do_action("delete", "secret", secret_name, "-n", system_project.project, "--ignore-not-found")
    )

    merged_kubeconfig = cluster.create_merged_kubeconfig(cluster2)
    result = kubectl_dns.add_cluster_secret(
        name=secret_name,
        context=cluster2.current_context_name,
        namespace=system_project.project,
        service_account="coredns",
        kubeconfig=merged_kubeconfig,
    )
    assert result.returncode == 0, f"kubectl-dns couldn't generate kubeconfig secret: {result.stderr}"
    return []


def test_kubectl_dns_secret_generation(hostname):
    """IPs from both, primary and secondary, clusters should return in DNS A record set"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"
