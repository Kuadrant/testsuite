"""conftest for limitador storage tests"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

LIMIT = Limit(5, "600s")


@pytest.fixture(scope="module")
def limitador(limitador, request, storage):
    """Setting storage option for tests and waiting until Limitador is ready"""
    request.addfinalizer(limitador.reset_storage)
    limitador.set_storage(storage)
    limitador.wait_for_ready()
    return limitador


@pytest.fixture(scope="function")
def rate_limit(cluster, blame, route, module_label):
    """Set a limit with a long window to allow for pod restart to finish inside the window"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rlp.add_limit("basic", [LIMIT])
    return rlp


@pytest.fixture(scope="function", autouse=True)
def commit(request, rate_limit, limitador):  # pylint: disable=unused-argument
    """
    Commits rate_limit before every test function to reset the counter
    limitador fixture is requested so the storage gets applied to all tests
    """
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
