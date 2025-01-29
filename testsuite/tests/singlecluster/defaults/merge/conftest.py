"""Conftest for merge strategy tests"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType


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
