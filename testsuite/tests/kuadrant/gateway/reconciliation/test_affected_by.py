"""Tests that affected by status is applied correctly to the HTTPRoute and Gateway"""

import pytest

from testsuite.policy.rate_limit_policy import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def rate_limit(openshift, blame, module_label, route):
    """
    Rate limit object.
    """

    policy = RateLimitPolicy.create_instance(openshift, blame("limit"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, 10)])
    return policy


def test_route_status(route, rate_limit, authorization):
    """Tests affected by status for HTTPRoute"""
    route.refresh()
    assert route.is_affected_by(rate_limit)
    assert route.is_affected_by(authorization)

    rate_limit.delete()
    assert not route.wait_until(lambda obj: obj.is_affected_by(rate_limit))

    authorization.delete()
    assert not route.wait_until(lambda obj: obj.is_affected_by(authorization))


@pytest.mark.dnspolicy
@pytest.mark.tlspolicy
def test_gateway_status(gateway, dns_policy, tls_policy):
    """Tests affected by status for Gateway"""
    gateway.refresh()
    assert gateway.is_affected_by(dns_policy)
    assert gateway.is_affected_by(tls_policy)

    dns_policy.delete()
    assert not gateway.wait_until(lambda obj: obj.is_affected_by(dns_policy))

    tls_policy.delete()
    assert not gateway.wait_until(lambda obj: obj.is_affected_by(tls_policy))
