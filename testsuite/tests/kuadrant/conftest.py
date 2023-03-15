"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""
import pytest

from testsuite.openshift.objects.auth_config.auth_policy import AuthPolicy


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
def authorization(authorino, kuadrant, envoy, authorization_name, openshift, module_label):
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    if kuadrant:
        policy = AuthPolicy.create_instance(
            openshift, authorization_name, envoy.route, labels={"testRun": module_label}
        )
        return policy
    return None


@pytest.fixture(scope="module")
def client(envoy):
    """Returns httpx client to be used for requests"""
    client = envoy.client()
    yield client
    client.close()


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
