"""Test merging override policies on gateway with policies on route without override."""

import pytest

from testsuite.kuadrant.policy import CelPredicate, has_condition
from testsuite.tests.singlecluster.defaults.test_basic_rate_limit import LIMIT
from testsuite.tests.singlecluster.overrides.merge.rate_limit.conftest import OVERRIDE_LIMIT2, OVERRIDE_LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Create a RateLimitPolicy with a basic limit with route as target"""
    route_when = CelPredicate("request.path == '/image'")
    rate_limit.add_limit("image_limit", [LIMIT], when=[route_when])
    return rate_limit


def test_gateway_override_merge(client, global_rate_limit, rate_limit):
    """Test RateLimitPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert global_rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been successfully enforced")
    )
    assert rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been partially enforced")
    )

    get = client.get_many("/get", OVERRIDE_LIMIT.limit)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", OVERRIDE_LIMIT2.limit)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

    get = client.get_many("/image", LIMIT.limit, headers={"accept": "image/webp"})
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
