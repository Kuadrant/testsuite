"""Test override overriding another policy aimed at the same gateway/route section"""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

LIMIT = Limit(8, "5s")
OVERRIDE_LIMIT = Limit(3, "5s")


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route) and the target section name"""
    return request.getfixturevalue(request.param[0]), request.param[1]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, target):
    """Add a RateLimitPolicy targeting the specific section of gateway/route"""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), target[0], section_name=target[1], labels={"testRun": module_label}
    )
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def override_rate_limit(cluster, blame, module_label, target):
    """Add a RateLimitPolicy targeting the specific section of gateway/route"""
    override_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), target[0], section_name=target[1], labels={"testRun": module_label}
    )
    override_rate_limit.overrides.add_limit("override", [OVERRIDE_LIMIT])
    return override_rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, override_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, override_rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize(
    "target",
    [pytest.param(("gateway", "api"), id="gateway"), pytest.param(("route", "rule-1"), id="route")],
    indirect=True,
)
def test_multiple_policies_listener_override(client):
    """Test RateLimitPolicy with an override overriding a default policy targeting the same gateway/route section"""
    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
