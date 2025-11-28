"""Tests for DNSPolicy health checks - healthy endpoint"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import HealthCheck, has_record_condition

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


def test_remove_endpoint(backend, hostname, dns_policy, dns_health_probe, client, auth):
    """Scale backend replicas to 0 and back to 1, and check if DNSPolicy will remove the unhealthy endpoint"""
    assert dns_health_probe.is_healthy()
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    backend.deployment.self_selector().scale(0)
    assert dns_policy.wait_until(has_condition("SubResourcesHealthy", "False"), timelimit=120)
    assert dns_policy.wait_until(
        has_record_condition("Healthy", "False", "HealthChecksFailed", "Not healthy addresses:")
    )

    assert dns_health_probe.wait_until(lambda obj: not obj.is_healthy())
    with hostname.client(retry_codes={}) as clean_client:
        response = clean_client.get("/get", auth=auth)
        assert response.status_code == 503

    backend.deployment.self_selector().scale(1)
    assert dns_policy.wait_until(has_condition("SubResourcesHealthy", "True"), timelimit=120)

    assert dns_health_probe.wait_until(lambda obj: obj.is_healthy())
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
