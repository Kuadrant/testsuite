"""Conftest for RLP section_name targeting tests"""

import pytest


@pytest.fixture(scope="module")
def route(route, backend):
    """Add two backend rules for different paths to the route"""
    route.remove_all_rules()
    route.add_backend(backend, "/get")
    route.add_backend(backend, "/anything")
    return route


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
