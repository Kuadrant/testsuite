"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""
import pytest


@pytest.fixture(scope="session")
def authorino():
    """Authorino instance when configured through Kuadrant"""
    return None


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorino, envoy, blame, openshift):
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    return None


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
