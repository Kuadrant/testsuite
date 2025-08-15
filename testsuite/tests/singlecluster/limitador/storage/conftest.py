"""conftest for limitador storage tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

LIMIT = Limit(5, "600s")


@pytest.fixture(scope="module")
def limitador(limitador, request, storage):
    """Setting storage option for tests and waiting until Limitador is ready"""
    request.addfinalizer(limitador.reset_storage)
    limitador.set_storage(storage)
    return limitador


@pytest.fixture(scope="function")
def rate_limit(rate_limit):
    """Set a limit with a long window to allow for pod restart to finish inside the window"""
    rate_limit.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="function", autouse=True)
def commit(request, rate_limit, limitador):
    """
    Commits rate_limit before every test function to reset the counter
    limitador fixture is requested so the storage gets applied to all tests
    """
    limitador.wait_for_ready()
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
