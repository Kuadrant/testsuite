"""Tests for OIDCPolicy with a confidential client (Authorization Code Flow)."""

from urllib.parse import quote

import jwt as jwt_lib
import pytest

from keycloak import KeycloakOpenID

from testsuite.oidc.keycloak.objects import ClientConfig
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create confidential OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("confidential"),
        public_client=False,
        redirect_uris=[f"http://{hostname.hostname}/*"],
        web_origins=[f"http://{hostname.hostname}"],
        root_url=f"http://{hostname.hostname}",
        service_accounts_enabled=True,
    )
    kc_client = keycloak.realm.create_client(**config.to_keycloak_payload())
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=kc_client.auth_id,
        realm_name=keycloak.realm_name,
        client_secret_key=kc_client.secret,
    )


def test_unauthenticated_redirect(client, keycloak_client, gateway):
    """Unauthenticated request redirects to OIDC provider with correct params."""
    response = client.get("/")
    assert response.status_code == 302
    assert "Location" in response.headers

    location = response.headers["Location"]
    assert "response_type=code" in location
    assert "scope=openid" in location
    assert keycloak_client.client_id in location

    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location


def test_jwt_cookie_authentication(client, auth):
    """Valid JWT cookie grants access."""
    with set_jwt_cookie(client, auth.access_token):
        response = client.get("/")
        assert response.status_code == 200


def test_token_claims(auth, keycloak_client, keycloak):
    """Confidential client token contains user identity claims."""
    token = jwt_lib.decode(auth.access_token, options={"verify_signature": False})

    assert token["typ"] == "Bearer"
    assert "openid" in token["scope"]
    assert token["azp"] == keycloak_client.client_id
    assert token["preferred_username"].lower() == keycloak.test_username.lower()
    assert "email" in token


def test_refresh_token_present(auth):
    """Confidential client token includes a refresh token."""
    assert auth.refresh_token is not None
    assert auth.refresh_function is not None
