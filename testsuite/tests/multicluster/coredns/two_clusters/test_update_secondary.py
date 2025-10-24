"""Test if update/delete changes on secondary DNSRecord are propagated to the authoritative DNS record"""

import dns.resolver
import pytest

from testsuite.utils import asdict
from testsuite.kubernetes.secret import Secret
from testsuite.utils import sleep_ttl
from testsuite.kuadrant.policy.dns import DNSRecordEndpoint
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


def test_update_secondary(hostname, dnsrecord2):
    """Test if update/delete changes on secondary DNSRecord are propagated to the authoritative DNS record"""
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, IP2} == dns_ips, "CoreDNS should have returned both IP addresses in A record set"

    new_ip = "79.1.35.254"
    dnsrecord2.model.spec.endpoints = [
        asdict(DNSRecordEndpoint(dnsName=hostname.hostname, recordType="A", recordTTL=60, targets=[new_ip]))
    ]
    dnsrecord2.apply()
    dnsrecord2.wait_for_ready()
    sleep_ttl(hostname.hostname)

    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1, new_ip} == dns_ips

    dnsrecord2.delete()
    sleep_ttl(hostname.hostname)

    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {IP1} == dns_ips
