"""
Test for wildcard host
"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization(authorino, blame, openshift, module_label, wildcard_domain):
    """In case of Authorino, AuthConfig used for authorization"""
    return AuthConfig.create_instance(
        openshift, blame("ac"), None, hostnames=[wildcard_domain], labels={"testRun": module_label}
    )


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
