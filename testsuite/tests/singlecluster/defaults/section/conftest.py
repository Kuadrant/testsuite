"""Conftest for RLP section_name targeting tests"""

import pytest


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, authorization):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [authorization, rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()
