"""Test defaults policy aimed at the same resoure uses oldested policy."""

import pytest

from .conftest import MERGE_LIMIT

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, default_merge_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, default_merge_rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("rate_limit", ["gateway", "route"], indirect=True)
def test_multiple_policies_merge_default_ab(client):
    """Test RateLimitPolicy with merge defaults being ingored due to age"""
    responses = client.get_many("/get", MERGE_LIMIT.limit)
    responses.assert_all(200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", MERGE_LIMIT.limit)
    responses.assert_all(200)
    assert client.get("/anything").status_code == 429
