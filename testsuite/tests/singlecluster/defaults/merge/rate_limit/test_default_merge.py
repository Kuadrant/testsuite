"""Test gateway level default merging with and being partially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import CelPredicate, has_condition
from testsuite.tests.singlecluster.defaults.merge.rate_limit.conftest import LIMIT, MERGE_LIMIT, MERGE_LIMIT2

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def route(backend, route):
    """Add 1 additional backend rules for specific backend paths"""
    route.add_backend(backend, "/image")
    return route


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Create a RateLimitPolicy with a basic limit with route as target"""
    route_when = CelPredicate("request.path == '/image'")
    rate_limit.add_limit("image_limit", [LIMIT], when=[route_when])
    return rate_limit


def test_gateway_default_merge(client, global_rate_limit, rate_limit):
    """Both policies are enforced and not being overridden"""
    assert global_rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been successfully enforced")
    )

    assert rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been successfully enforced")
    )

    get = client.get_many("/get", MERGE_LIMIT.limit)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", MERGE_LIMIT2.limit)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

    get = client.get_many("/image", LIMIT.limit, headers={"accept": "image/webp"})
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429
