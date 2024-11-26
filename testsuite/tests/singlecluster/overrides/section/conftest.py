"""Conftest for overrides section_name targeting tests."""

import pytest


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, override_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, override_rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()
