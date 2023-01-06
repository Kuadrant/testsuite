"""Tests basic authentication with RHSSO/Auth0 as identity provider"""
import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc import OIDCProvider
from testsuite.oidc.rhsso import RHSSO


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add RHSSO identity to AuthConfig"""
    authorization.identity.oidc("rhsso", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module", params=("rhsso", "auth0"))
def oidc_provider(request) -> OIDCProvider:
    """Fixture which enables switching out OIDC providers for individual modules"""
    return request.getfixturevalue(request.param)


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization_name(blame, oidc_provider):
    """Ensure for every oidc_provider we have a unique authorization"""
    return blame("authz")


@pytest.fixture(scope="module")
def wrong_auth(oidc_provider, auth0, rhsso):
    """Different (but valid) auth than was configured"""
    token = rhsso.get_token
    if isinstance(oidc_provider, RHSSO):
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


# pylint: disable=unused-argument
def test_no_auth(client):
    """Tests request without any auth"""
    response = client.get("/get")
    assert response.status_code == 401


# pylint: disable=unused-argument
def test_invalid_auth(client):
    """Tests request with invalid token"""
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
