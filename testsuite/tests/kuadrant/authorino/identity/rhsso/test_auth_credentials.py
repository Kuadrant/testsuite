"""Test for RHSSO auth credentials"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.objects import Credentials


@pytest.fixture(scope="module", params=["authorization_header", "custom_header", "query", "cookie"])
def credentials(request):
    """Location where are auth credentials passed"""
    return request.param


@pytest.fixture(scope="module")
def authorization(rhsso, openshift, blame, route, module_label, credentials):
    """Add RHSSO identity to AuthConfig"""
    authorization = AuthConfig.create_instance(openshift, blame("ac"), route, labels={"testRun": module_label})
    authorization.identity.add_oidc("rhsso", rhsso.well_known["issuer"], credentials=Credentials(credentials, "Token"))
    return authorization


def test_custom_selector(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"authorization": "Token " + auth.token.access_token})
    assert response.status_code == 200 if credentials == "authorization_header" else 401


def test_custom_header(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"Token": auth.token.access_token})
    assert response.status_code == 200 if credentials == "custom_header" else 401


def test_query(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", params={"Token": auth.token.access_token})
    assert response.status_code == 200 if credentials == "query" else 401


def test_cookie(route, auth, credentials):
    """Test if auth credentials are stored in right place"""
    with route.client(cookies={"Token": auth.token.access_token}) as client:
        response = client.get("/get")
        assert response.status_code == 200 if credentials == "cookie" else 401
