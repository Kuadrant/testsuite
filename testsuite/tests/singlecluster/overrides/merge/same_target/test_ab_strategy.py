"""Test override policy aimed at the same resource always takes precedence."""

import pytest

from testsuite.kuadrant.policy import has_condition
from .conftest import OVERRIDE_LIMIT, OVERRIDE_LIMIT2

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, override_merge_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, override_merge_rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


def test_multiple_policies_merge_default_ab(client, rate_limit, override_merge_rate_limit):
    """Test RateLimitPolicy with merge overrides always being enforced"""
    assert rate_limit.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "RateLimitPolicy is overridden by "
            f"[{override_merge_rate_limit.namespace()}/{override_merge_rate_limit.name()}]",
        )
    )

    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", OVERRIDE_LIMIT2.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
