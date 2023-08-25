"""Test condition to skip the identity section of AuthConfig"""
import pytest

from testsuite.objects import Rule
from testsuite.httpx.auth import HeaderApiKeyAuth


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Create API key"""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def auth(api_key):
    """Create auth from Api Key"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Add to the AuthConfig API key identity, which can only be used on requests to the /get path"""
    when_get = [Rule("context.request.http.path", "eq", "/get")]
    authorization.identity.add_api_key("api-key", selector=api_key.selector, when=when_get)
    return authorization


def test_skip_identity(client, auth):
    """Send request to /get and /post, verify that API key evaluator is not used on /get requests"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.post("/post", auth=auth)
    assert response.status_code == 401
