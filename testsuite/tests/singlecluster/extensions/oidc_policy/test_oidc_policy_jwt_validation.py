"""Tests for OIDCPolicy JWT validation (client-type independent)."""

import pytest

from keycloak import KeycloakOpenID

from testsuite.oidc.keycloak.objects import ClientConfig
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create confidential OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("jwt-validation"),
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


def test_malformed_jwt(client):
    """Malformed JWT is rejected and redirects to auth."""
    with set_jwt_cookie(client, "not.a.jwt"):
        response = client.get("/")
        assert response.status_code == 302


def test_tampered_jwt_signature(client, auth):
    """JWT with tampered signature is rejected."""
    parts = auth.access_token.split(".")
    assert len(parts) == 3, "Invalid JWT token format"

    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature"
    with set_jwt_cookie(client, tampered_token):
        response = client.get("/")
        assert response.status_code == 302
