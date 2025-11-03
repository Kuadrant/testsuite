"""Test if removal of DNSRecords will also clean them up on the provider"""

import dns.resolver
import pytest

from testsuite.utils import is_nxdomain
from testsuite.kubernetes.secret import Secret
from testsuite.utils import sleep_ttl
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


def test_authoritative_record_removal_cleans_up_provider(hostname, dnsrecord1, dnsrecord2):
    """Delete DNSRecords from both primary and secondary clusters and check they are really cleaned up"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"

    dnsrecord2.delete()
    sleep_ttl(hostname.hostname)
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1} == dns_ips, "CoreDNS should have only returned the primary IP address in A record set"

    authoritative_record = dnsrecord1.get_authoritative_dns_record()
    assert authoritative_record.exists()[0], "Authoritative DNSRecord should still exist"

    dnsrecord1.delete()
    sleep_ttl(hostname.hostname)
    assert not authoritative_record.exists()[0], "Authoritative DNSRecord should be cleaned up"
    assert is_nxdomain(hostname.hostname)
