"""
Tests the DNS Endpoint Provider aggregation logic.

Verifies that endpoints from multiple Source DNSRecords are correctly merged into
a single Destination DNSRecord (Zone) and successfully resolved via the upstream provider.
"""

import pytest
import dns.resolver
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint
from testsuite.kubernetes.secret import Secret

SOURCE_IP1 = "91.16.35.100"
SOURCE_IP2 = "172.6.13.223"

pytestmark = [pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def endpoint_provider_secret(request, cluster, module_label, blame):
    """Creates a fresh endpoint provider secret in the test namespace"""
    secret_data = {
        "ENDPOINT_GVR": "kuadrant.io/v1alpha1.dnsrecords",
        "ENDPOINT_ZONE_RECORD_LABEL": "kuadrant.io/zone-record=true",
    }

    secret = Secret.create_instance(
        cluster,
        blame("endpoint-creds"),
        secret_data,
        secret_type="kuadrant.io/endpoint",
        labels={"app": module_label},
    )

    request.addfinalizer(secret.delete)
    secret.commit()
    return secret.name()


@pytest.fixture(scope="module")
def destination_dnsrecord(cluster, blame, hostname, dns_provider_secret, module_label):
    """Destination Record acting as the Zone"""
    record = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("dest-zone"),
        root_host=hostname.hostname,
        delegate=False,
        provider_ref_name=dns_provider_secret,
        labels={"app": module_label, "kuadrant.io/zone-record": "true"},
    )
    return record


@pytest.fixture(scope="module")
def source_dnsrecords(cluster, blame, hostname, endpoint_provider_secret, module_label):
    """Source Records acting as endpoint feeders"""
    dns_name_1 = f"src1.{hostname.hostname}"
    dns_name_2 = f"src2.{hostname.hostname}"

    source1 = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("src-1"),
        root_host=hostname.hostname,
        endpoints=[DNSRecordEndpoint(dnsName=dns_name_1, recordType="A", recordTTL=60, targets=[SOURCE_IP1])],
        delegate=False,
        provider_ref_name=endpoint_provider_secret,
        labels={"app": module_label},
    )

    source2 = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("src-2"),
        root_host=hostname.hostname,
        endpoints=[DNSRecordEndpoint(dnsName=dns_name_2, recordType="A", recordTTL=60, targets=[SOURCE_IP2])],
        delegate=False,
        provider_ref_name=endpoint_provider_secret,
        labels={"app": module_label},
    )

    return [source1, source2]


@pytest.fixture(scope="module", autouse=True)
def commit(request, destination_dnsrecord, source_dnsrecords):
    """Commits the DNSRecords to the cluster and handles cleanup"""
    all_records = [destination_dnsrecord] + source_dnsrecords

    for record in all_records:
        request.addfinalizer(record.delete)
        record.commit()
        record.wait_for_ready()


def test_records_accessible(hostname):
    """Verify that endpoints are merged and accessible via DNS"""
    src1_answers = dns.resolver.resolve(f"src1.{hostname.hostname}")
    src2_answers = dns.resolver.resolve(f"src2.{hostname.hostname}")

    assert len(src1_answers) == 1
    assert len(src2_answers) == 1

    assert src1_answers[0].address == SOURCE_IP1
    assert src2_answers[0].address == SOURCE_IP2
