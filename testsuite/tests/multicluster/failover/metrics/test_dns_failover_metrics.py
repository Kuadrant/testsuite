"""Test DNS failover group metrics exposed by the DNS Operator on both clusters"""

import operator

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.prometheus import has_label

pytestmark = [pytest.mark.multicluster, pytest.mark.dnspolicy, pytest.mark.disruptive, pytest.mark.flaky(reruns=0)]


def test_dns_record_group_info(dns_metrics, dns_metrics2, dns_record, dns_record2, group1, group2):
    """Test dns_record_group_info gauge reports group assignment on both clusters"""
    group1_info = dns_metrics.filter(has_label("__name__", "dns_record_group_info")).filter(has_label("group", group1))
    assert len(group1_info.metrics) == 1, f"Expected 1 dns_record_group_info metric for {group1} on cluster1"
    assert group1_info.metrics[0]["metric"]["dns_record_name"] == dns_record.name()
    assert group1_info.metrics[0]["metric"]["dns_record_namespace"] == dns_record.namespace()

    group2_info = dns_metrics2.filter(has_label("__name__", "dns_record_group_info")).filter(has_label("group", group2))
    assert len(group2_info.metrics) == 1, f"Expected 1 dns_record_group_info metric for {group2} on cluster2"
    assert group2_info.metrics[0]["metric"]["dns_record_name"] == dns_record2.name()
    assert group2_info.metrics[0]["metric"]["dns_record_namespace"] == dns_record2.namespace()


def test_dns_record_group_active(dns_metrics, dns_metrics2, dns_record, dns_record2, group1, group2):
    """Test dns_record_group_active gauge reports active/inactive state on both clusters"""
    group1_active = dns_metrics.filter(has_label("__name__", "dns_record_group_active")).filter(
        has_label("group", group1)
    )
    assert len(group1_active.metrics) == 1, f"Expected 1 dns_record_group_active metric for {group1} on cluster1"
    assert group1_active.metrics[0]["metric"]["dns_record_name"] == dns_record.name()
    assert group1_active.values[0] == 1.0

    group2_active = dns_metrics2.filter(has_label("__name__", "dns_record_group_active")).filter(
        has_label("group", group2)
    )
    assert len(group2_active.metrics) == 1, f"Expected 1 dns_record_group_active metric for {group2} on cluster2"
    assert group2_active.metrics[0]["metric"]["dns_record_name"] == dns_record2.name()
    assert group2_active.values[0] == 0.0


def test_dns_record_inactive_group_cleanup_total(
    dns_metrics, cluster, exposer, dns_provider_secret, dns_policy2, group1, group2, kubectl_dns, prometheus
):
    """Test cleanup counter increments after group activation and deactivation"""
    cleanup = dns_metrics.filter(has_label("__name__", "dns_record_inactive_group_cleanup_total")).filter(
        has_label("group", group1)
    )
    assert len(cleanup.metrics) == 0, "Cleanup counter should not exist before any group deactivation"

    provider_ref = f"{cluster.project}/{dns_provider_secret}"

    result = kubectl_dns.add_active_group(cluster, group2, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to add group2 to active groups: {result.stderr}"

    dns_records2 = dns_policy2.get_dns_records()
    assert len(dns_records2) == 1
    assert dns_records2[0].wait_until(
        has_condition("Ready", "True", "ProviderSuccess"), timelimit=300
    ), f"DNSRecord on cluster2 should become ready, got: {dns_records2[0].model.status.conditions}"

    result = kubectl_dns.remove_active_group(cluster, group2, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to remove group2 from active groups: {result.stderr}"

    assert dns_records2[0].wait_until(
        has_condition("Active", "False", "NotMemberOfActiveGroup", "Group is not included in active groups"),
        timelimit=120,
    ), f"DNSRecord on cluster2 should report inactive group, got: {dns_records2[0].model.status.conditions}"

    # Counter is emitted by group1's operator on cluster1 when it cleans up group2's stale records
    assert prometheus.wait_for_metric(
        "dns_record_inactive_group_cleanup_total", 1, labels={"group": group1}, compare=operator.ge
    ), "Cleanup counter should increment after group deactivation"
