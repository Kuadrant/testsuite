"""Test condition to skip the identity section of AuthConfig"""
import pytest

from testsuite.objects import Rule
from testsuite.httpx.auth import HeaderApiKeyAuth


@pytest.fixture(scope="module")
def auth(create_api_key, module_label):
    """Create API key and return his auth"""
    api_key = create_api_key("api-key", module_label, "api_key_value")
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, module_label):
    """Add to the AuthConfig API key identity, which can only be used on requests to the /get path"""
    when_get = [Rule("context.request.http.path", "eq", "/get")]
    authorization.identity.api_key("api-key", match_label=module_label, when=when_get)
    return authorization


def test_skip_identity(client, auth):
    """Send request to /get and /post, verify that API key evaluator is not used on /get requests"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.post("/post", auth=auth)
    assert response.status_code == 401
