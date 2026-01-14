"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.tests.singlecluster.defaults.merge.rate_limit.conftest import MERGE_LIMIT, MERGE_LIMIT2

pytestmark = [pytest.mark.defaults_overrides, pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, global_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, global_rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()
        policy.wait_for_ready()


@pytest.mark.parametrize(
    "rate_limit, global_rate_limit",
    [("gateway", "gateway"), ("route", "route")],
    indirect=True,
)
def test_multiple_policies_merge_default_ab(client, rate_limit, global_rate_limit):
    """Test RateLimitPolicy with merge defaults being enforced due to age"""
    assert rate_limit.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "RateLimitPolicy is overridden by " f"[{global_rate_limit.namespace()}/{global_rate_limit.name()}]",
        )
    )

    responses = client.get_many("/get", MERGE_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", MERGE_LIMIT2.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
