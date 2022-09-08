"""
Tests for multiple auth identities (RHSSO + Auth0)
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="module")
def auth0_auth(auth0):
    """Returns Auth0 authentication object for HTTPX"""
    return HttpxOidcClientAuth(auth0.get_token)


@pytest.fixture(scope="module")
def rhsso_auth(rhsso):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso.get_token)


@pytest.fixture(scope="module")
def authorization(authorization, auth0, rhsso):
    """Add both RHSSO and Auth0 identities"""
    authorization.add_oidc_identity("rhsso", rhsso.well_known["issuer"])
    authorization.add_oidc_identity("auth0", auth0.well_known["issuer"])
    return authorization


def test_correct_auth(client, rhsso_auth, auth0_auth):
    """Tests correct auth"""
    response = client.get("/get", auth=rhsso_auth)
    assert response.status_code == 200

    response = client.get("/get", auth=auth0_auth)
    assert response.status_code == 200


def test_no_auth(client):
    """Tests request without any auth"""
    response = client.get("/get")
    assert response.status_code == 401


def test_wrong_auth(client):
    """Tests request with wrong token"""
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
