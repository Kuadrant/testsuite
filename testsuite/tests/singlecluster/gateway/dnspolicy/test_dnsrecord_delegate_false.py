"""
Test DNSRecord with delegate=false and providerRef set to external DNS provider.
Verifies that the record is created on the provider and is accessible.
"""

import pytest

import dns.resolver
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint

pytestmark = [pytest.mark.dnspolicy]

TEST_IP = "123.5.7.12"


@pytest.fixture(scope="module")
def dns_record(cluster, hostname, dns_provider_secret, blame, module_label):
    """Create DNSRecord with delegate=false and providerRef"""

    # Create DNSRecord with delegate=false and provider reference
    record = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("dnsrecord"),
        root_host=hostname.hostname,
        endpoints=[DNSRecordEndpoint(dnsName=hostname.hostname, recordType="A", recordTTL=300, targets=[TEST_IP])],
        delegate=False,
        provider_ref_name=dns_provider_secret,
        labels={"app": module_label},
    )

    return record


@pytest.fixture(scope="module", autouse=True)
def commit(request, dns_record):
    """Commit the DNSRecord and ensure cleanup"""
    request.addfinalizer(dns_record.delete)
    dns_record.commit()
    dns_record.wait_for_ready()


def test_dns_record_delegate_false_with_provider(hostname):
    """Test that DNSRecord with delegate=false creates accessible DNS record"""

    answers = dns.resolver.resolve(hostname.hostname, "A")
    resolved_ip = answers[0].to_text()
    assert resolved_ip == TEST_IP, f"Expected {TEST_IP}, got {resolved_ip}"
