"""Test for API key auth credentials"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


@pytest.fixture(scope="module", params=["authorization_header", "custom_header", "query", "cookie"])
def credentials(request):
    """Location where are auth credentials passed"""
    return request.param


@pytest.fixture(scope="module")
def authorization(openshift, blame, envoy, module_label, credentials):
    """Add API key identity to AuthConfig"""
    authorization = AuthConfig.create_instance(openshift, blame("ac"), envoy.route, labels={"testRun": module_label})
    authorization.identity.api_key("api_key", match_label=module_label, credentials=credentials, selector="API_KEY")
    return authorization


def test_custom_selector(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"authorization": "API_KEY " + auth.api_key})
    assert response.status_code == 200 if credentials == "authorization_header" else 401


def test_custom_header(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"API_KEY": auth.api_key})
    assert response.status_code == 200 if credentials == "custom_header" else 401


def test_query(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", params={"API_KEY": auth.api_key})
    assert response.status_code == 200 if credentials == "query" else 401


def test_cookie(envoy, auth, credentials):
    """Test if auth credentials are stored in right place"""
    with envoy.client(cookies={"API_KEY": auth.api_key}) as client:
        response = client.get("/get")
        assert response.status_code == 200 if credentials == "cookie" else 401
