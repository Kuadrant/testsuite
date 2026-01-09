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
DUMMY_IP = "127.0.0.1"

pytestmark = [pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def endpoint_provider_secret(request, cluster, module_label, blame):
    """Creates a fresh endpoint provider secret in the test namespace"""
    secret_data = {"AWS_ACCESS_KEY_ID": "DUMMYACCESSKEY", "AWS_SECRET_ACCESS_KEY": "DUMMYSECRETKEY"}

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
    dummy_endpoint = DNSRecordEndpoint(dnsName=hostname.hostname, recordType="A", recordTTL=300, targets=[DUMMY_IP])

    record = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("dest-zone"),
        root_host=hostname.hostname,
        endpoints=[dummy_endpoint],
        delegate=False,
        labels={"app": module_label, "kuadrant.io/zone-record": "true"},
    )
    record.model["spec"]["providerRef"] = {"name": dns_provider_secret}
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
        labels={"app": module_label},
    )
    source1.model["spec"]["providerRef"] = {"name": endpoint_provider_secret}

    source2 = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("src-2"),
        root_host=hostname.hostname,
        endpoints=[DNSRecordEndpoint(dnsName=dns_name_2, recordType="A", recordTTL=60, targets=[SOURCE_IP2])],
        delegate=False,
        labels={"app": module_label},
    )
    source2.model["spec"]["providerRef"] = {"name": endpoint_provider_secret}

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
    assert SOURCE_IP1 in {r.address for r in dns.resolver.resolve(f"src1.{hostname.hostname}")}
    assert SOURCE_IP2 in {r.address for r in dns.resolver.resolve(f"src2.{hostname.hostname}")}
