"""Test condition to skip the authorization section of AuthConfig"""

import pytest

from testsuite.policy.authorization import Pattern

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add to the AuthConfig authorization with opa policy that will always reject POST requests"""
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.authorization.add_opa_policy("opa", "allow { false }", when=when_post)
    return authorization


def test_skip_authorization(client, auth):
    """Send GET and POST requests to the same endpoint, verify if authorization has been skipped on GET request"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.post("/post", auth=auth)
    assert response.status_code == 403
