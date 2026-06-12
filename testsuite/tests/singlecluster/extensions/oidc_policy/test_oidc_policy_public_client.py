"""Tests for OIDCPolicy with a public client (Authorization Code Flow + PKCE)."""

from urllib.parse import quote

import jwt as jwt_lib
import pytest

from keycloak import KeycloakOpenID

from testsuite.oidc import Token
from testsuite.oidc.keycloak.objects import ClientConfig
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create public OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("public"),
        client_type="public",
        public_client=True,
        redirect_uris=[f"http://{hostname.hostname}/*"],
        web_origins=[f"http://{hostname.hostname}"],
        root_url=f"http://{hostname.hostname}",
    )
    kc_client = keycloak.realm.create_client(**config.to_keycloak_payload())
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=kc_client.auth_id,
        realm_name=keycloak.realm_name,
    )


@pytest.fixture(scope="module")
def auth(keycloak_client, keycloak):
    """Get a Token for the test user."""

    def _refresh(refresh_token):
        data = keycloak_client.refresh_token(refresh_token)
        return Token(data["access_token"], _refresh, data.get("refresh_token", ""))

    data = keycloak_client.token(keycloak.test_username, keycloak.test_password)
    return Token(data["access_token"], _refresh, data.get("refresh_token", ""))


def test_unauthenticated_redirect(client, keycloak_client, gateway):
    """Unauthenticated request redirects to OIDC provider with PKCE params."""
    response = client.get("/")
    assert response.status_code == 302
    assert "Location" in response.headers

    location = response.headers["Location"]
    assert "response_type=code" in location
    assert "scope=openid" in location
    assert keycloak_client.client_id in location
    assert "code_challenge" in location or "response_type=code" in location

    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location


def test_jwt_cookie_authentication(client, auth):
    """Valid JWT cookie grants access."""
    with set_jwt_cookie(client, auth.access_token):
        response = client.get("/")
        assert response.status_code == 200


def test_token_claims(auth, keycloak_client, keycloak):
    """Public client token contains user identity claims."""
    token = jwt_lib.decode(auth.access_token, options={"verify_signature": False})

    assert token["typ"] == "Bearer"
    assert "openid" in token["scope"]
    assert token["azp"] == keycloak_client.client_id
    assert token["preferred_username"].lower() == keycloak.test_username.lower()
    assert "email" in token
