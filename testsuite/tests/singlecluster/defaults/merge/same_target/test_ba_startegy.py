"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from .conftest import LIMIT, MERGE_LIMIT2

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, default_merge_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [default_merge_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


def test_multiple_policies_merge_default_ba(client, default_merge_rate_limit):
    """Test RateLimitPolicy with merge defaults being ignored due to age"""
    assert default_merge_rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been partially enforced")
    )

    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", MERGE_LIMIT2.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
