"""Test merging override policies on gateway with policies on route with partial override."""

import pytest

from testsuite.kuadrant.policy import CelPredicate, has_condition
from testsuite.tests.singlecluster.overrides.merge.rate_limit.conftest import LIMIT, OVERRIDE_LIMIT2, OVERRIDE_LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Create a RateLimitPolicy with a basic limit with same target as one default."""
    when = CelPredicate("request.path == '/get'")
    rate_limit.add_limit("get_limit", [LIMIT], when=[when])
    return rate_limit


def test_gateway_override_replace(client, global_rate_limit, rate_limit):
    """Test RateLimitPolicy with an override and merge strategy overrides completely the lower level one"""
    assert rate_limit.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "RateLimitPolicy is overridden by " f"[{global_rate_limit.namespace()}/{global_rate_limit.name()}]",
        )
    )

    get = client.get_many("/get", OVERRIDE_LIMIT.limit)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", OVERRIDE_LIMIT2.limit)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
