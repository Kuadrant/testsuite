"""
Test for plain identity.

Plain identity expects authentication/identity verification to be done in advance and a trusted identity object
being accessible from AuthJson in given path.
If path does not exist or there is a null value there the request is not authorized (401).
If path exists the value is copied over to `auth.identity` of AuthJson and 200 OK is returned

See also https://github.com/Kuadrant/authorino/blob/main/docs/features.md#plain-authenticationplain

There is no authentication/identity verification done, the test just picks HTTP method as if it was an identity object.
"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(
            {"path": "context.nonexistent.path", "code": 401, "identity": None},
            id="non-existent AuthJson path to retrieve identity from",
        ),
        pytest.param(
            {"path": "context.request.http.method", "code": 200, "identity": "GET"},
            id="existing AuthJson path to retrieve identity from",
        ),
    ],
)
def plain_identity(request):
    """AuthJson path the identity is retrieved from"""
    return request.param


@pytest.fixture(scope="module")
def authorization(authorization, plain_identity):
    """
    Setup AuthConfig to retrieve identity from given path
    """
    authorization.identity.add_plain("plain", plain_identity["path"])
    authorization.responses.add_simple("auth.identity")
    return authorization


def test_plain_identity(client, plain_identity):
    """
    Setup:
        - Create AuthConfig with plain identity object configured to be retrieved from given path from AuthJson
    Test:
        - Send request
        - Assert that response status code is as expected (200 OK / 401 Unauthorized)
        - Assert that identity is populated with expected value based on given path (in case of 200 OK)
    """
    response = client.get("/get")
    assert response.status_code == plain_identity["code"]

    identity = extract_response(response)
    # identity should be populated with the value retrieved from AuthJson in the specified path
    assert identity % None == plain_identity["identity"]
