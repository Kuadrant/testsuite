"""Tests that affected by status is applied correctly to the HTTPRoute and Gateway"""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """
    Rate limit object.
    """

    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    return policy


@pytest.mark.authorino
@pytest.mark.limitador
def test_route_status(route, rate_limit, authorization):
    """Tests affected by status for HTTPRoute"""
    route.refresh()
    assert route.is_affected_by(rate_limit)
    assert route.is_affected_by(authorization)

    rate_limit.delete()
    assert route.wait_until(lambda obj: not obj.is_affected_by(rate_limit))

    authorization.delete()
    assert route.wait_until(lambda obj: not obj.is_affected_by(authorization))


@pytest.mark.dnspolicy
@pytest.mark.tlspolicy
def test_gateway_status(gateway, dns_policy, tls_policy):
    """Tests affected by status for Gateway"""
    gateway.refresh()
    assert gateway.is_affected_by(dns_policy)
    assert gateway.is_affected_by(tls_policy)

    dns_policy.delete()
    assert gateway.wait_until(lambda obj: not obj.is_affected_by(dns_policy))

    tls_policy.delete()
    assert gateway.wait_until(lambda obj: not obj.is_affected_by(tls_policy))
