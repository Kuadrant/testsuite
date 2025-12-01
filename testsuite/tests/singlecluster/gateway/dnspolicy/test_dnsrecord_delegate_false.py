"""
Test DNSRecord with delegate=false and providerRef set to external DNS provider.
Verifies that the record is created on the provider and is accessible.
"""

import pytest

import backoff
import dns.resolver
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def dns_record(cluster, gateway, base_domain, dns_provider_secret, blame, module_label):
    """Create DNSRecord with delegate=false and providerRef"""
    test_hostname = f"{blame('test')}.{base_domain}"

    # Get IP from gateway for the endpoint
    gateway_ip = gateway.external_ip().split(":")[0]  # Remove port if present

    # Create DNSRecord with delegate=false and provider reference
    record = DNSRecord.create_instance(
        cluster=cluster,
        name=blame("dnsrecord"),
        root_host=test_hostname,
        endpoints=[DNSRecordEndpoint(dnsName=test_hostname, recordType="A", recordTTL=300, targets=[gateway_ip])],
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


def test_dns_record_delegate_false_with_provider(dns_record):
    """Test that DNSRecord with delegate=false creates accessible DNS record"""

    # Verify it's ready with ProviderSuccess
    assert any(
        c.type == "Ready" and c.status == "True" and c.reason == "ProviderSuccess"
        for c in dns_record.model.status.conditions
    ), "DNSRecord not ready with ProviderSuccess"

    # Verify DNS resolution works
    @backoff.on_exception(
        backoff.fibo, (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout), max_time=120
    )
    def check_dns():
        answers = dns.resolver.resolve(dns_record.model.spec.rootHost, "A")
        expected_ip = dns_record.model.spec.endpoints[0].targets[0]
        resolved_ip = answers[0].to_text()
        assert resolved_ip == expected_ip, f"Expected {expected_ip}, got {resolved_ip}"

    check_dns()
