"""Tests for DNSPolicy health checks - healthy endpoint"""

import pytest

from testsuite.kuadrant.policy.dns import HealthCheck

pytestmark = [pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def health_check():
    """Returns healthy endpoint specification for DNSPolicy health check"""
    return HealthCheck(
        path="/get",
        interval="5s",
        protocol="HTTPS",
        port=443,
    )


def test_healthy_endpoint(dns_health_probe, client, auth):
    """Test healthy endpoint check"""
    assert dns_health_probe.is_healthy()

    response = client.get("/get", auth=auth)
    assert response.status_code == 200
