"""Conftest for rate limit tests"""

import pytest


@pytest.fixture(scope="module")
def kuadrant(kuadrant):
    """Skip if not running on Kuadrant"""
    if not kuadrant:
        pytest.skip("Limitador test can only run on Kuadrant for now")
    return kuadrant


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
