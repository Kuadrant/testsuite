"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""

import pytest

from testsuite.policy.authorization.auth_policy import AuthPolicy
from testsuite.policy.rate_limit_policy import RateLimitPolicy


@pytest.fixture(scope="session")
def run_on_kuadrant():
    """True, if the tests should pass when running on Kuadrant"""
    return True


@pytest.fixture(scope="module", autouse=True)
def skip_no_kuadrant(kuadrant, run_on_kuadrant):
    """Skips all tests that are not working with Kuadrant"""
    if kuadrant and not run_on_kuadrant:
        pytest.skip("This test doesn't work with Kuadrant")


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorino(kuadrant, skip_no_kuadrant):
    """Authorino instance when configured through Kuadrant"""
    if kuadrant:
        # No available modification
        return True
    return None


@pytest.fixture(scope="module")
def authorization_name(blame):
    """Name of the Authorization resource, can be overriden to include more dependencies"""
    return blame("authz")


@pytest.fixture(scope="module")
def authorization(authorino, kuadrant, oidc_provider, route, authorization_name, openshift, module_label):
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    if kuadrant:
        return AuthPolicy.create_instance(openshift, authorization_name, route, labels={"testRun": module_label})
    return None


@pytest.fixture(scope="module")
def rate_limit(kuadrant, openshift, blame, request, module_label, route, gateway):
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
