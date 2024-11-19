"""Tests for DNSPolicy health checks - unhealthy endpoint"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import HealthCheck, has_record_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def health_check():
    """Returns unhealthy endpoint specification for DNSPolicy health check"""
    return HealthCheck(
        path="/unknown-endpoint",
        interval="5s",
        protocol="HTTPS",
        port=443,
    )


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, tls_policy, dns_policy):  # pylint: disable=unused-argument
    """Commits tlspolicy and dnspolicy without waiting for dnspolicy to be enforced"""
    request.addfinalizer(tls_policy.delete)
    tls_policy.commit()
    tls_policy.wait_for_ready()

    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()


def test_unhealthy_endpoint(dns_policy, dns_health_probe, client, auth):
    """Test unhealthy endpoint check"""
    assert not dns_health_probe.is_healthy()
    response = client.get("/get", auth=auth)
    assert response.has_dns_error()

    assert dns_policy.wait_until(has_condition("Enforced", "False"))
    assert dns_policy.wait_until(
        has_record_condition("Ready", "False", "HealthChecksFailed", "Not publishing unhealthy records")
    )
