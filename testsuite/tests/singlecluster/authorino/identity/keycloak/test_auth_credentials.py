"""Test for Keycloak auth credentials"""

import pytest

from testsuite.kuadrant.policy.authorization import Credentials

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module", params=["authorizationHeader", "customHeader", "queryString", "cookie"])
def credentials(request):
    """Location where are auth credentials passed"""
    return request.param


@pytest.fixture(scope="module")
def authorization(authorization, keycloak, credentials):
    """Add Keycloak identity to Authorization"""
    authorization.identity.add_oidc(
        "keycloak", keycloak.well_known["issuer"], credentials=Credentials(credentials, "Token")
    )
    return authorization


def test_custom_selector(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"authorization": "Token " + auth.token.access_token})
    if credentials == "authorizationHeader":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_custom_header(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"Token": auth.token.access_token})
    if credentials == "customHeader":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_query(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", params={"Token": auth.token.access_token})
    if credentials == "queryString":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_cookie(hostname, auth, credentials):
    """Test if auth credentials are stored in right place"""
    with hostname.client(cookies={"Token": auth.token.access_token}) as client:
        response = client.get("/get")
        if credentials == "cookie":
            assert response.status_code == 200
        else:
            assert response.status_code == 401
