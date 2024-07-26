"""Conftest for rate limit tests"""

import pytest


@pytest.fixture(scope="session")
def limitador(kuadrant):
    """Returns Limitador CR"""

    return kuadrant.limitador


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
