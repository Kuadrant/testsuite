"""
Test for wildcard host
"""
import pytest

from testsuite.policy.authorization.auth_config import AuthConfig


@pytest.fixture(scope="module")
def route(route, wildcard_domain, hostname):
    """Set route for wildcard domain"""
    route.add_hostname(wildcard_domain)
    route.remove_hostname(hostname.hostname)
    return route


@pytest.fixture(scope="module")
def authorization(blame, route, openshift, module_label):
    """In case of Authorino, AuthConfig used for authorization"""
    return AuthConfig.create_instance(openshift, blame("ac"), route, labels={"testRun": module_label})


def test_wildcard(client):
    """
    Preparation:
        - Create AuthConfig with host set to wildcard domain
    Test:
        - Send request to authorino
        - Assert that request was successful
    """
    response = client.get("/get")
    assert response.status_code == 200
