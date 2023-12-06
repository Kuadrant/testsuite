"""Tests for DNSPolicy health checks - unhealthy endpoint"""
import pytest

from testsuite.policy.dns_policy import HealthCheck

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def health_check():
    """Returns unhealthy endpoint specification for DNSPolicy health check"""
    return HealthCheck(
        allowInsecureCertificates=True,
        endpoint="/unknown-endpoint",
        interval="5s",
        port=80,
        protocol="http",
    )


def test_unhealthy_endpoint(dns_health_probe):
    """Test unhealthy endpoint check"""
    assert not dns_health_probe.is_healthy()
