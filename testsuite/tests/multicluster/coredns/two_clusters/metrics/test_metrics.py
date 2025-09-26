"""Test multi-cluster CoreDNS metrics exposed by the DNS Operator on /metrics endpoint"""

import pytest

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def dns_metrics(prometheus, service_monitor):
    """Return all metrics from the DNS Operator controller /metrics endpoint"""
    prometheus.wait_for_scrape(service_monitor, "/metrics")
    return prometheus.get_metrics(labels={"service": "dns-operator-controller-manager-metrics-service"})


def test_authoritative_record_metrics(testconfig, dns_metrics, dnsrecord1):
    """Test metrics for the authoritative DNSRecord on the primary cluster"""
    authoritative_record = dns_metrics.filter(
        lambda x: x["metric"].get("dns_record_name") == dnsrecord1.model.status.zoneID
    )

    authoritative_record_metric = authoritative_record.filter(
        lambda x: x["metric"].get("dns_record_name") == dnsrecord1.model.status.zoneID
        and x["metric"].get("dns_record_is_delegating") == "false"
    )
    assert len(authoritative_record_metric.metrics) == 1
    assert (
        authoritative_record_metric.metrics[0]["metric"]["dns_record_root_host"]
        == f'ns1.{testconfig["dns"]["coredns_zone"]}'
    )

    authoritative_write_metric = authoritative_record.filter(
        lambda x: x["metric"]["__name__"] == "dns_provider_write_counter"
    )
    assert len(authoritative_write_metric.metrics) == 1

    dns_provider_authoritative_record_spec_info = authoritative_record.filter(
        lambda x: x["metric"]["__name__"] == "dns_provider_authoritative_record_spec_info"
    )

    assert len(dns_provider_authoritative_record_spec_info.metrics) == 1
    assert (
        dns_provider_authoritative_record_spec_info.metrics[0]["metric"]["root_host"]
        == f'ns1.{testconfig["dns"]["coredns_zone"]}'
    )
    assert dns_provider_authoritative_record_spec_info.values[0] == 1


def test_delegating_record_metrics(testconfig, dns_metrics, dnsrecord1, dnsrecord2):
    """Test metrics for 2 delegating DNSRecords"""
    for rec in [dnsrecord1, dnsrecord2]:
        delegating_record_metrics = dns_metrics.filter(
            lambda x, record_name=rec.name(): x["metric"].get("dns_record_name") == record_name
        )

        delegating_record = delegating_record_metrics.filter(
            lambda x: x["metric"].get("dns_record_is_delegating") == "true"
        )
        assert len(delegating_record.metrics) == 1
        assert (
            delegating_record.metrics[0]["metric"]["dns_record_root_host"] == f'ns1.{testconfig["dns"]["coredns_zone"]}'
        )
        assert delegating_record.metrics[0]["metric"]["dns_record_namespace"] == rec.namespace()
        assert delegating_record.names[0] == "dns_provider_record_ready"
        assert delegating_record.values[0] == 1.0

        assert "dns_provider_write_counter" in delegating_record_metrics.names


def test_multi_cluster_count_metrics(dns_metrics):
    """Test metric for active multi-cluster kubeconfig secrets loaded"""
    dns_provider_active_multi_cluster_count = dns_metrics.filter(
        lambda x: x["metric"]["__name__"] == "dns_provider_active_multi_cluster_count"
    )
    assert len(dns_provider_active_multi_cluster_count.metrics) == 1
    assert dns_provider_active_multi_cluster_count.values[0] == 1


def test_remote_records_metrics(dns_metrics, kubeconfig_secrets):
    """Test metrics for remote records loaded from secondary clusters"""
    dns_provider_remote_records_metrics = dns_metrics.filter(
        lambda x: x["metric"].get("cluster") == kubeconfig_secrets[0].name()
    )

    dns_provider_remote_records = dns_provider_remote_records_metrics.filter(
        lambda x: x["metric"]["__name__"] == "dns_provider_remote_records"
    )
    assert len(dns_provider_remote_records.metrics) == 1
    assert dns_provider_remote_records.values[0] == 1

    assert "dns_provider_remote_record_reconcile_count" in dns_provider_remote_records_metrics.names
