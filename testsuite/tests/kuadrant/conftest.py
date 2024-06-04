"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""

import pytest
from openshift_client import selector, OpenShiftPythonException

from testsuite.config import settings
from testsuite.openshift.authorino import AuthorinoCR
from testsuite.openshift.limitador import LimitadorCR
from testsuite.policy.authorization.auth_policy import AuthPolicy
from testsuite.policy.rate_limit_policy import RateLimitPolicy


@pytest.fixture(scope="session")
def system_openshift():
    """Returns client for Kuadrant"""
    ocp = settings["service_protection"]["project"]
    project = settings["service_protection"]["system_project"]
    return ocp.change_project(project)


@pytest.fixture(scope="session")
def authorino(system_openshift) -> AuthorinoCR:
    """Authorino instance when configured through Kuadrant"""
    try:
        with system_openshift.context:
            authorino = selector("authorino").object(cls=AuthorinoCR)
            authorino.committed = True
    except OpenShiftPythonException:
        pytest.fail("Running Kuadrant tests, but Authorino resource was not found")

    return authorino


@pytest.fixture(scope="session")
def limitador(system_openshift) -> LimitadorCR:
    """Returns Limitador CR"""
    try:
        with system_openshift.context:
            limitador = selector("limitador").object(cls=LimitadorCR)
            limitador.committed = True
    except OpenShiftPythonException:
        pytest.fail("Running Kuadrant tests, but Limitador resource was not found")

    return limitador


@pytest.fixture(scope="module")
def authorization_name(blame):
    """Name of the Authorization resource, can be overriden to include more dependencies"""
    return blame("authz")


@pytest.fixture(scope="module")
def authorization(kuadrant, route, authorization_name, openshift, label):
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    if kuadrant:
        return AuthPolicy.create_instance(openshift, authorization_name, route, labels={"testRun": label})
    return None


@pytest.fixture(scope="module")
def rate_limit(kuadrant, openshift, blame, request, module_label, route, gateway):  # pylint: disable=unused-argument
    """
    Rate limit object.
    Request is used for indirect parametrization, with two possible parameters:
        1. `route` (default)
        2. `gateway`
    """
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        return RateLimitPolicy.create_instance(openshift, blame("limit"), target_ref, labels={"testRun": module_label})
    return None


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()
