"""
Test for authorino redirect
"""
import pytest

from testsuite.objects import ValueFrom, DenyResponse

STATUS_CODE = 302
REDIRECT_URL = "http://anything.inavlid?redirect_to="


@pytest.fixture(scope="module")
def authorization(authorization):
    """In case of Authorino, AuthConfig used for authorization"""
    authorization.responses.set_unauthenticated(
        DenyResponse(
            code=STATUS_CODE,
            headers={"Location": ValueFrom(REDIRECT_URL + "{context.request.http.path}")},
        )
    )
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
