"""Test rate limit policies collisions when attached to the same target"""

import pytest

from testsuite.kuadrant.policy import has_condition, CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy


FIRST_LIMIT = Limit(3, "5s")
SECOND_LIMIT = Limit(6, "5s")

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route)"""
    return request.getfixturevalue(request.param)


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def rate_limit(request, cluster, blame, module_label, target, label):
    """Create a RateLimitPolicy with either gateway or route as target reference"""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("fp"), target, labels={"testRun": module_label})
    rate_limit.add_limit("first", [FIRST_LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.fixture(scope="module")
def rate_limit2(request, cluster, blame, module_label, target, label):
    """Create a second RateLimitPolicy with with the same target as the first RateLimitPolicy"""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), target, labels={"testRun": module_label})
    rate_limit.add_limit("second", [SECOND_LIMIT], when=[CelPredicate("request.path == '/anything'")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, rate_limit2):
    """Commits RateLimitPolicies after the target is created"""
    for policy in [rate_limit, rate_limit2]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("target", ["gateway", "route"], indirect=True)
def test_collision_rate_limit(client, rate_limit, rate_limit2):
    """Test first policy is being overridden when another policy with the same target is created."""
    assert rate_limit.wait_until(has_condition("Enforced", "False", "Overridden", "RateLimitPolicy is overridden"))
    responses = client.get_many("/get", FIRST_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 200

    responses = client.get_many("/anything", SECOND_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
