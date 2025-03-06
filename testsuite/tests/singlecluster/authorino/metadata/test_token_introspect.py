"""
Test for checking I OAuth 2.0 access tokens (e.g. opaque tokens) for online user data and token validation in
request-time.
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/oauth2-token-introspection.md
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def client_secret(create_client_secret, keycloak, blame):
    """create the required secrets that will be used by Authorino to authenticate with Keycloak"""
    return create_client_secret(blame("secret"), keycloak.client.auth_id, keycloak.client.secret)


@pytest.fixture(scope="function")
def _auth(oidc_provider):
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def authorization(client_secret, authorization, keycloak):
    """
    On every request, Authorino will try to verify the token remotely with the Keycloak server with the introspect
    endpoint. It's credentials are referenced from the secret created before.
    """
    authorization.identity.add_oauth2_introspection("default", keycloak, client_secret)
    return authorization


def test_no_token(client):
    """Test access with no auth"""
    response = client.get("get")
    assert response.status_code == 401


def test_access_token(client, _auth):
    """Tests auth with token granted from fixture"""
    response = client.get("get", auth=_auth)
    assert response.status_code == 200


def test_revoked_token(client, _auth, keycloak):
    """Revoke token by logging out and test if is unauthorized"""
    keycloak.oidc_client.logout(_auth.token.refresh_token)
    response = client.get("get", auth=_auth)
    assert response.status_code == 401
