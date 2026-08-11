"""Test DNS failover from one cluster to another using DNS Operator active groups"""

import time

import dns.resolver
import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.utils import sleep_ttl

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive, pytest.mark.flaky(reruns=0)]


def test_dns_failover(
    cluster,
    exposer,
    client,
    hostname,
    dns_provider_secret,
    gateway,
    gateway2,
    dns_policy,
    dns_policy2,
    dns_operator_deployment,
    kubectl_dns,
    group1,
    group2,
):  # pylint: disable=too-many-locals
    """
    Test DNS failover from group1 (cluster1) to group2 (cluster2):
    1. Verify initial state with DNS resolving to cluster1
    2. Add group2 to active groups and verify DNS resolves to both clusters
    3. Scale down DNS operator on cluster1 and remove group1 from active groups
    4. Verify DNS resolves to cluster2 after failover
    5. Scale up DNS operator on cluster1 and verify it reports inactive group
    """
    gw1_ip = gateway.external_ip().split(":")[0]
    gw2_ip = gateway2.external_ip().split(":")[0]

    dns_records = dns_policy.get_dns_records()
    dns_records2 = dns_policy2.get_dns_records()
    assert len(dns_records) == 1
    assert len(dns_records2) == 1
    dns_record = dns_records[0]
    dns_record2 = dns_records2[0]

    response = client.get("/get")
    assert not response.has_dns_error(), response.error
    assert response.status_code == 200
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {gw1_ip} == dns_ips, f"Initially DNS should only resolve to cluster1 IP ({gw1_ip}), got {dns_ips}"

    # add second cluster group to active groups and verify that both clusters are in the active groups now
    provider_ref = f"{cluster.project}/{dns_provider_secret}"
    result = kubectl_dns.add_active_group(cluster, group2, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to add group2 to active groups: {result.stderr}"
    assert dns_record.wait_until(
        has_condition("Active", "True", "MemberOfActiveGroup", "Group is included in active groups")
    ), f"dns_record should report active group, got: {dns_record.model.status.conditions}"
    assert dns_record2.wait_until(
        has_condition("Active", "True", "MemberOfActiveGroup", "Group is included in active groups")
    ), f"dns_record2 should report active group, got: {dns_record2.model.status.conditions}"
    sleep_ttl(hostname.hostname)
    time.sleep(10)  # arbitrary sleep after all the required waits because test won't succeed without it for some reason

    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {
        gw1_ip,
        gw2_ip,
    } == dns_ips, f"After adding group2 DNS should resolve to both cluster IPs ({gw1_ip}, {gw2_ip}), got {dns_ips}"

    # scale down DNS operator on cluster1 to simulate failure and remove the first cluster group from active groups
    dns_operator_deployment.set_replicas(0)
    result = kubectl_dns.remove_active_group(cluster, group1, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to remove group1 from active groups: {result.stderr}"
    assert dns_record2.wait_until(
        has_condition("Active", "True", "MemberOfActiveGroup", "Group is included in active groups")
    ), f"dns_record2 should report active group, got: {dns_record2.model.status.conditions}"
    sleep_ttl(hostname.hostname)
    time.sleep(60)  # arbitrary sleep after all the required waits because test won't succeed without it for some reason

    response = client.get("/get")
    assert not response.has_dns_error(), response.error
    assert response.status_code == 200
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {gw2_ip} == dns_ips, f"After failover DNS should only resolve to cluster2 IP ({gw2_ip}), got {dns_ips}"

    # scale up DNS operator back to the working state and verify that the first cluster DNS operator updated the status
    dns_operator_deployment.set_replicas(1)
    assert dns_record.wait_until(
        has_condition("Active", "False", "NotMemberOfActiveGroup", "Group is not included in active groups")
    ), f"dns_record should report inactive group, got: {dns_record.model.status.conditions}"
