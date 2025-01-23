"""Conftest for RLP section_name targeting tests"""

import pytest

from testsuite.gateway import PathMatch, RouteMatch, MatchType


@pytest.fixture(scope="module")
def route(route, backend):
    """Add two new rules to the route"""
    route.remove_all_rules()
    route.add_rule(
        backend,
        RouteMatch(path=PathMatch(value="/get", type=MatchType.PATH_PREFIX)),
    )
    route.add_rule(
        backend,
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX)),
    )
    return route


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
