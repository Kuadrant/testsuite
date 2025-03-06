"""Test defaults policy aimed at the same resoure uses oldested policy."""

import pytest

from .conftest import LIMIT, MERGE_LIMIT2

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, default_merge_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [default_merge_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


def test_multiple_policies_merge_default_ba(client):
    """Test RateLimitPolicy with merge defaults being enforced due to age"""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", MERGE_LIMIT2.limit)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
