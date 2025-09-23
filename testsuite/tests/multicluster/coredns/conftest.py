"""Shared fixtures for all coredns tests"""

import pytest

from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint

# random test IPs for the DNS records
IP1 = "91.16.35.100"
IP2 = "172.6.13.223"


@pytest.fixture(scope="module")
def set_delegate_mode():
    """Delegate mode placeholder so cluster delegation mode can be changed at the very beginning of the test session"""


@pytest.fixture(scope="module")
def coredns_secrets(
    request, set_delegate_mode, testconfig, cluster, cluster2, blame, module_label
):  # pylint: disable=unused-argument
    """CoreDNS secrets for both clusters"""
    secret_name = blame("coredns")
    for c in [cluster, cluster2]:
        secret = Secret.create_instance(
            c,
            secret_name,
            {"ZONES": testconfig["dns"]["coredns_zone"]},
            secret_type="kuadrant.io/coredns",
            labels={"kuadrant.io/default-provider": "true", "app": module_label},
        )
        request.addfinalizer(secret.delete)
        secret.commit()


@pytest.fixture(scope="module")
def dnsrecord1(cluster, testconfig, blame, module_label):
    """Return a DNSRecord instance ready for commit"""
    return DNSRecord.create_instance(
        cluster,
        blame("rcrd1"),
        f'ns1.{testconfig["dns"]["coredns_zone"]}',
        endpoints=[
            DNSRecordEndpoint(
                dnsName=f'ns1.{testconfig["dns"]["coredns_zone"]}', recordType="A", recordTTL=60, targets=[IP1]
            )
        ],
        delegate=True,
        labels={"app": module_label},
    )


@pytest.fixture(scope="module")
def dnsrecord2(cluster2, testconfig, blame, module_label):
    """Return a DNSRecord instance ready for commit"""
    return DNSRecord.create_instance(
        cluster2,
        blame("rcrd2"),
        f'ns1.{testconfig["dns"]["coredns_zone"]}',
        endpoints=[
            DNSRecordEndpoint(
                dnsName=f'ns1.{testconfig["dns"]["coredns_zone"]}', recordType="A", recordTTL=60, targets=[IP2]
            )
        ],
        delegate=True,
        labels={"app": module_label},
    )
