"""
Tests the DNS Endpoint Provider aggregation logic.

Verifies that endpoints from multiple Source DNSRecords are correctly merged into
a single Destination DNSRecord (Zone) and successfully resolved via the upstream provider.
"""

import pytest
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint

SOURCE_IP1 = "91.16.35.100"
SOURCE_IP2 = "172.6.13.223"
DUMMY_IP = "127.0.0.1"

pytestmark = [pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def endpoint_provider_secret():
    """Returns the name of the endpoint provider secret"""
    return "dns-provider-credentials-endpoint"


@pytest.fixture(scope="module")
def aws_provider_secret():
    """Returns the name of the AWS provider secret"""
    return "aws-credentials"


@pytest.fixture(scope="module")
def shared_hostname(base_domain, blame):
    """Returns the shared hostname used for aggregation"""
    return f"{blame('app')}.{base_domain}"


@pytest.fixture(scope="module")
def destination_dnsrecord(cluster, blame, shared_hostname, aws_provider_secret, module_label):
    """Destination Record acting as the Zone"""
    dummy_endpoint = DNSRecordEndpoint(dnsName=shared_hostname, recordType="A", recordTTL=300, targets=[DUMMY_IP])

    record = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("dest-zone"),
        root_host=shared_hostname,
        endpoints=[dummy_endpoint],
        delegate=False,
        labels={"app": module_label, "kuadrant.io/zone-record": "true"},
    )
    record.model["spec"]["providerRef"] = {"name": aws_provider_secret}
    return record


@pytest.fixture(scope="module")
def source_dnsrecords(cluster, blame, shared_hostname, endpoint_provider_secret, module_label):
    """Source Records acting as endpoint feeders"""
    dns_name_1 = f"src1.{shared_hostname}"
    dns_name_2 = f"src2.{shared_hostname}"

    source1 = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("src-1"),
        root_host=shared_hostname,
        endpoints=[DNSRecordEndpoint(dnsName=dns_name_1, recordType="A", recordTTL=60, targets=[SOURCE_IP1])],
        delegate=False,
        labels={"app": module_label},
    )
    source1.model["spec"]["providerRef"] = {"name": endpoint_provider_secret}

    source2 = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("src-2"),
        root_host=shared_hostname,
        endpoints=[DNSRecordEndpoint(dnsName=dns_name_2, recordType="A", recordTTL=60, targets=[SOURCE_IP2])],
        delegate=False,
        labels={"app": module_label},
    )
    source2.model["spec"]["providerRef"] = {"name": endpoint_provider_secret}

    return [source1, source2]


@pytest.fixture(scope="module", autouse=True)
def commit(request, destination_dnsrecord, source_dnsrecords):
    """Commits the DNSRecords to the cluster and handles cleanup"""
    request.addfinalizer(destination_dnsrecord.delete)
    destination_dnsrecord.commit()
    destination_dnsrecord.wait_for_ready()

    for record in source_dnsrecords:
        request.addfinalizer(record.delete)
        record.commit()


def test_endpoint_provider_configuration(destination_dnsrecord, source_dnsrecords, endpoint_provider_secret):
    """Verify configuration and labels"""
    destination_dnsrecord.refresh()
    assert destination_dnsrecord.model.metadata.labels.get("kuadrant.io/zone-record") == "true"

    for record in source_dnsrecords:
        record.refresh()
        assert record.model.spec.providerRef.name == endpoint_provider_secret
        assert record.model.spec.rootHost == destination_dnsrecord.model.spec.rootHost


def test_records_accessible(destination_dnsrecord, shared_hostname):
    """Verify that endpoints are merged and accessible via DNS"""
    # 1. Verify Merge
    destination_dnsrecord.wait_for_endpoints_merged({SOURCE_IP1, SOURCE_IP2})
    # 2. Verify DNS Resolution
    destination_dnsrecord.wait_until_resolves(f"src1.{shared_hostname}", SOURCE_IP1)
    destination_dnsrecord.wait_until_resolves(f"src2.{shared_hostname}", SOURCE_IP2)
