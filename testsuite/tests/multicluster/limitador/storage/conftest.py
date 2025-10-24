"""Conftest for general multicluster Limitador storage tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy


@pytest.fixture(scope="module")
def configured_limitador1(limitador1, request, storage1):
    """Applies `storage1` config to the first Limitador and waits for it to be ready."""
    request.addfinalizer(limitador1.reset_storage)
    limitador1.set_storage(storage1)
    limitador1.wait_for_ready()
    return limitador1


@pytest.fixture(scope="module")
def configured_limitador2(limitador2, request, storage2):
    """Applies `storage2` config to the second Limitador and waits for it to be ready."""
    request.addfinalizer(limitador2.reset_storage)
    limitador2.set_storage(storage2)
    limitador2.wait_for_ready()
    return limitador2


@pytest.fixture(scope="function")
def rate_limit_policy1(routes, limit, cluster, rate_limit_name):
    """Creates a RateLimitPolicy object for the first cluster."""
    route = routes[0]
    rlp = RateLimitPolicy.create_instance(cluster, rate_limit_name, route)
    rlp.add_limit("global", [limit])
    return rlp


@pytest.fixture(scope="function")
def rate_limit_policy2(routes, limit, cluster2, rate_limit_name):
    """Creates a RateLimitPolicy object for the second cluster."""
    route = routes[1]
    rlp = RateLimitPolicy.create_instance(cluster2, rate_limit_name, route)
    rlp.add_limit("global", [limit])
    return rlp

@pytest.fixture(scope="function")
def rate_limit_name(blame):
    return blame("rlp")


@pytest.fixture(scope="function", autouse=True)
def commit_policies(request, rate_limit_policy1, rate_limit_policy2, configured_limitador1, configured_limitador2):
    """Commits both RateLimitPolicies before the test runs and registers their cleanup."""
    request.addfinalizer(rate_limit_policy1.delete)
    request.addfinalizer(rate_limit_policy2.delete)
    rate_limit_policy1.commit()
    rate_limit_policy2.commit()
    rate_limit_policy1.wait_for_ready()
    rate_limit_policy2.wait_for_ready()

