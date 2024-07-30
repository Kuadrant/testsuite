"""Conftest for rate limit tests"""

import pytest
from openshift_client import selector, OpenShiftPythonException

from testsuite.kuadrant.limitador import LimitadorCR


@pytest.fixture(scope="session")
def limitador(cluster, testconfig) -> LimitadorCR:
    """Returns Limitador CR"""
    system_openshift = cluster.change_project(testconfig["service_protection"]["system_project"])

    try:
        with system_openshift.context:
            limitador = selector("limitador").object(cls=LimitadorCR)
    except OpenShiftPythonException:
        pytest.fail("Running Kuadrant tests, but Limitador resource was not found")

    return limitador


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
