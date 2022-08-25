"""
Test for wildcard host
"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization(authorino, blame, openshift, module_label):
    """In case of Authorino, AuthConfig used for authorization"""
    return AuthConfig.create_instance(openshift, blame("ac"), "*.redhat.com", labels={"testRun": module_label})


def test_wildcard(client):
    """
    Preparation:
        - Create AuthConfig with host set to `*.redhat.com`
    Test:
        - Send request to authorino
        - Assert that request was successful
    """
    response = client.get("/get")
    assert response.status_code == 200
