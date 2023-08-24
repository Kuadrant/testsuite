"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""
import pytest

from testsuite.openshift.objects.auth_config.auth_policy import AuthPolicy
from testsuite.openshift.objects.rate_limit import RateLimitPolicy


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
        policy = AuthPolicy.create_instance(openshift, authorization_name, route, labels={"testRun": module_label})
        policy.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
        return policy
    return None


@pytest.fixture(scope="module")
def rate_limit_name(blame):
    """Name of the rate limit"""
    return blame("limit")


@pytest.fixture(scope="module")
def rate_limit(kuadrant, openshift, rate_limit_name, route, module_label):
    """Rate limit"""
    if kuadrant:
        return RateLimitPolicy.create_instance(openshift, rate_limit_name, route, labels={"testRun": module_label})
    return None


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()


@pytest.fixture(scope="module")
def client(route):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = route.client()
    yield client
    client.close()
