import pytest

from testsuite.gateway import MatchType, PathMatch, RouteMatch
from testsuite.kuadrant.policy import CelPredicate, Strategy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

LIMIT = Limit(8, "5s")
OVERRIDE_LIMIT = Limit(6, "5s")


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


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    basic_when = [
        CelPredicate("request.path == '/get'"),
    ]
    rate_limit.add_limit("basic", [LIMIT], when=basic_when)
    return rate_limit


@pytest.fixture(scope="module")
def override_merge_rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    policy = RateLimitPolicy.create_instance(cluster, blame("omp"), route, labels={"testRun": module_label})
    basic_when = [
        CelPredicate("request.path == '/get'"),
    ]
    override_when = [
        CelPredicate("request.path == '/anything'"),
    ]
    policy.overrides.add_limit("basic", [OVERRIDE_LIMIT], when=basic_when)
    policy.overrides.add_limit("override", [OVERRIDE_LIMIT], when=override_when)
    policy.strategy(Strategy.MERGE)
    return policy
