"""Test rate limit policies collisions when attached to the same target"""

import pytest

from testsuite.kuadrant.policy import has_condition, CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

FIRST_LIMIT = Limit(3, "5s")
SECOND_LIMIT = Limit(6, "5s")


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def rate_limit(request, cluster, blame, module_label, route, label):
    """Create a RateLimitPolicy with a basic limit with target coming from test parameter"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    rate_limit = RateLimitPolicy.create_instance(cluster, blame("fp"), target_ref, labels={"testRun": module_label})
    rate_limit.add_limit("first", [FIRST_LIMIT], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.fixture(scope="module")
def rate_limit2(request, cluster, blame, module_label, route, label):
    """Create a RateLimitPolicy with a basic limit with target coming from test parameter"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), target_ref, labels={"testRun": module_label})
    rate_limit.add_limit("second", [SECOND_LIMIT], when=[CelPredicate("request.path == '/anything'")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, rate_limit2):
    """Commits RateLimitPolicy after the target is created"""
    for policy in [rate_limit, rate_limit2]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("rate_limit", ["gateway", "route"], indirect=True)
def test_collision_rate_limit(client, rate_limit, rate_limit2):
    """Test first policy is being overridden when another policy with the same target is created."""
    assert rate_limit.wait_until(has_condition("Enforced", "False", "Overridden", "RateLimitPolicy is overridden"))
    responses = client.get_many("/get", FIRST_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 200

    responses = client.get_many("/anything", SECOND_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
