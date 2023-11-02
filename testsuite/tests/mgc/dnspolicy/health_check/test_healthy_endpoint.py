"""Tests for DNSPolicy health checks - healthy endpoint"""
import pytest

from testsuite.openshift.objects.dnspolicy import HealthCheck

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def health_check():
    """Returns healthy endpoint specification for DNSPolicy health check"""
    return HealthCheck(
        allowInsecureCertificates=True,
        endpoint="/get",
        interval="5s",
        port=80,
        protocol="http",
    )


def test_healthy_endpoint(dns_health_probe):
    """Test healthy endpoint check"""
    assert dns_health_probe.is_healthy()
