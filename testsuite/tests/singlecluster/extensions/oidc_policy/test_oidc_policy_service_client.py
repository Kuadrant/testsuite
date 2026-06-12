"""Tests for OIDCPolicy with a service client (Client Credentials Flow)."""

import jwt as jwt_lib
import pytest

from keycloak import KeycloakOpenID

from testsuite.oidc import Token
from testsuite.oidc.keycloak.objects import ClientConfig
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create service OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("service"),
        client_type="service",
        public_client=False,
        standard_flow_enabled=False,
        service_accounts_enabled=True,
        redirect_uris=[f"http://{hostname.hostname}/*"],
        web_origins=[f"http://{hostname.hostname}"],
        root_url=f"http://{hostname.hostname}",
        direct_access_grants_enabled=False,
    )
    kc_client = keycloak.realm.create_client(**config.to_keycloak_payload())
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=kc_client.auth_id,
        realm_name=keycloak.realm_name,
        client_secret_key=kc_client.secret,
    )


@pytest.fixture(scope="module")
def auth(keycloak_client):
    """Get a Token using client credentials grant."""

    def _refresh(refresh_token):
        data = keycloak_client.refresh_token(refresh_token)
        return Token(data["access_token"], _refresh, data.get("refresh_token", ""))

    data = keycloak_client.token(grant_type="client_credentials")
    return Token(data["access_token"], _refresh, data.get("refresh_token", ""))


def test_unauthenticated_redirect(client):
    """Unauthenticated request redirects to OIDC provider."""
    response = client.get("/")
    assert response.status_code == 302


def test_jwt_cookie_authentication(client, auth):
    """Valid service account JWT cookie grants access."""
    with set_jwt_cookie(client, auth.access_token):
        response = client.get("/")
        assert response.status_code == 200


def test_token_claims(auth, keycloak_client):
    """Service client token has client context but no user identity."""
    token = jwt_lib.decode(auth.access_token, options={"verify_signature": False})

    assert token["typ"] == "Bearer"
    assert "openid" in token["scope"]
    assert token["azp"] == keycloak_client.client_id
    assert token.get("preferred_username") != "testuser"
