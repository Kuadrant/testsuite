"""Test for RHSSO auth credentials"""
import pytest

from testsuite.objects import Credentials


@pytest.fixture(scope="module", params=["authorization_header", "custom_header", "query", "cookie"])
def credentials(request):
    """Location where are auth credentials passed"""
    return request.param


@pytest.fixture(scope="module")
def authorization(authorization, rhsso, credentials):
    """Add RHSSO identity to Authorization"""
    authorization.identity.clear_all()
    authorization.identity.add_oidc("rhsso", rhsso.well_known["issuer"], credentials=Credentials(credentials, "Token"))
    return authorization


def test_custom_selector(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"authorization": "Token " + auth.token.access_token})
    if credentials == "authorization_header":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_custom_header(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"Token": auth.token.access_token})
    if credentials == "custom_header":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_query(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", params={"Token": auth.token.access_token})
    if credentials == "query":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_cookie(route, auth, credentials):
    """Test if auth credentials are stored in right place"""
    with route.client(cookies={"Token": auth.token.access_token}) as client:
        response = client.get("/get")
        if credentials == "cookie":
            assert response.status_code == 200
        else:
            assert response.status_code == 401
