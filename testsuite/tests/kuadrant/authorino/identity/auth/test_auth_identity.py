"""Tests basic authentication with Keycloak/Auth0 as identity provider"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc import OIDCProvider
from testsuite.oidc.keycloak import Keycloak

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add Keycloak identity to AuthConfig"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module", params=("keycloak", "auth0"))
def oidc_provider(request) -> OIDCProvider:
    """Fixture which enables switching out OIDC providers for individual modules"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def wrong_auth(oidc_provider, auth0, keycloak):
    """Different (but valid) auth than was configured"""
    token = keycloak.get_token
    if isinstance(oidc_provider, Keycloak):
        token = auth0.get_token
    return HttpxOidcClientAuth(token)


def test_correct_auth(client, auth):
    """Tests correct auth"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_wrong_auth(wrong_auth, client):
    """Tests request with wrong token"""
    response = client.get("/get", auth=wrong_auth)
    assert response.status_code == 401


def test_no_auth(client):
    """Tests request without any auth"""
    response = client.get("/get")
    assert response.status_code == 401


def test_invalid_auth(client):
    """Tests request with invalid token"""
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
