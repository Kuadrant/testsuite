"""
Test for authorino redirect
"""
# pylint: disable=unused-argument
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig

STATUS_CODE = 302
REDIRECT_URL = 'http://anything.inavlid?redirect_to='


@pytest.fixture(scope="module")
def authorization(authorino, envoy, blame, openshift, module_label, oidc_provider):
    """In case of Authorino, AuthConfig used for authorization"""
    authorization = AuthConfig.create_instance(openshift, blame("ac"),
                                               envoy.hostname, labels={"testRun": module_label})
    authorization.set_deny_with(STATUS_CODE, REDIRECT_URL + "{context.request.http.path}")
    return authorization


def test_redirect(client, auth):
    """
    Preparation:
        - Setup authorino to redirect to another page and customize response status code
    Test:
        - Send request with valid authentication
        - Assert that status code of response is 200
        - Send request without valid authentication
        - Assert that status code of response is 302
        - Assert that redirect has the right URL
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get")
    assert response.status_code == STATUS_CODE
    assert response.next_request.url == REDIRECT_URL + "/get"
