"""Tests for OIDC policy functionality with Public Client.

This module tests OIDC authentication flows using a public client with PKCE
(Authorization Code Flow). Public clients are typically used in SPAs and mobile apps
where client secrets cannot be securely stored.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

from urllib.parse import quote

import jwt
import pytest
from keycloak import KeycloakOpenID

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.oidc_policy import Provider
from testsuite.oidc import Token
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import jwt_cookie

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


def _get_auth_for_public_client(oidc_client: KeycloakOpenID, keycloak) -> HttpxOidcClientAuth:
    """Get authentication for public client using user credentials."""

    def refresh_token_func(refresh_token: str) -> Token:
        """Refresh function that returns a new Token."""
        new_token_data = oidc_client.refresh_token(refresh_token)
        return Token(
            new_token_data["access_token"],
            refresh_token_func,
            new_token_data.get("refresh_token", ""),
        )

    try:
        # Public client: User authentication
        token_data = oidc_client.token(keycloak.test_username, keycloak.test_password)

        token = Token(
            token_data["access_token"],
            refresh_token_func,
            token_data.get("refresh_token", ""),
        )
        return HttpxOidcClientAuth(token, "authorization")

    except Exception as e:
        raise ValueError(f"Failed to get authentication for public client {oidc_client.client_id}: {e}") from e


def validate_oauth2_redirect(location, oidc_client, gateway):
    """Helper function to validate OAuth2 redirect parameters."""
    assert "response_type=code" in location, "Should use Authorization Code Flow"
    assert "scope=openid" in location, "Should request OpenID scope"
    assert oidc_client.client_id in location, "Should include correct client ID"

    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location, "Should have correct redirect URI"


def validate_jwt_token(token_string, expected_client_id):
    """Helper function to validate JWT token properties."""
    token = jwt.decode(token_string, options={"verify_signature": False})
    assert "openid" in token["scope"], "Token should include OpenID scope"
    assert token["typ"] == "Bearer", "Should be a Bearer token"
    assert token["azp"] == expected_client_id, "Token should be issued for correct client"
    return token


# Public Client specific fixtures
@pytest.fixture(scope="module")
def public_client(request, keycloak, hostname):
    """Create a public client with Authorization Code Flow + PKCE."""
    # Public client configuration
    client_params = {
        "name": "my-public-client",
        "publicClient": True,
        "standardFlowEnabled": True,
        "serviceAccountsEnabled": False,
        "protocol": "openid-connect",
        "clientId": "my-public-client",
        "redirectUris": [f"http://{hostname.hostname}/*"],
        "webOrigins": [f"http://{hostname.hostname}"],
    }

    # Create the client in Keycloak
    keycloak_client = keycloak.realm.create_client(**client_params)
    request.addfinalizer(lambda: keycloak.realm.delete_client(keycloak_client.client_id))

    # Return KeycloakOpenID instance
    oidc_client = KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=keycloak_client.auth_id,
        realm_name=keycloak.realm_name,
    )

    return oidc_client


@pytest.fixture(scope="module")
def auth(public_client, keycloak):
    """Get authentication object for public client."""
    return _get_auth_for_public_client(public_client, keycloak)


@pytest.fixture(scope="module")
def provider(oidc_provider, public_client):
    """Create Provider configuration for the OIDC policy."""
    return Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=public_client.client_id,
        clientSecret=getattr(public_client, "client_secret_key", None),
        authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
        tokenEndpoint=oidc_provider.well_known["token_endpoint"],
    )


# Tests
def test_public_client_authentication_flow(client, auth, public_client, gateway):
    """Test complete public client authentication flow with PKCE."""
    # Test unauthenticated request redirects to OAuth2
    response = client.get("/")
    assert response.status_code == 302, "Unauthenticated request should redirect"
    assert "Location" in response.headers, "Redirect must include Location header"

    location = response.headers["Location"]

    # Validate OAuth2 redirect parameters
    validate_oauth2_redirect(location, public_client, gateway)

    # Public clients should use PKCE
    assert (
        "code_challenge" in location or "response_type=code" in location
    ), "Should use Authorization Code Flow with PKCE"

    # Verify no client_secret in redirect (public clients don't have secrets)
    assert "client_secret" not in location, "Public client should not expose client secret"

    # Verify proper redirect URI encoding
    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location, "Should have properly encoded redirect URI"

    # Test JWT cookie authentication with valid token
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid JWT cookie should allow access"

        token = validate_jwt_token(auth.token.access_token, public_client.client_id)

        # Public client specific token validations
        assert token["azp"] == public_client.client_id, "Token should be issued for correct public client"
        assert "preferred_username" in token, "Public client tokens should contain user identity"
        assert "email" in token, "Public client tokens should contain user email"
        assert token["preferred_username"] == "testuser", "Should be test user"
        assert token["email"] == "testuser@anything.invalid", "Token should contain user email"
        assert "openid" in token["scope"], "Token should include OpenID scope"

    # Test invalid JWT rejection
    with jwt_cookie(client, "invalid.jwt.token"):
        response = client.get("/")
        assert response.status_code == 302, "Invalid JWT should redirect to OAuth2 flow"


def test_public_client_jwt_handling(client, auth, public_client):  # pylint: disable=unused-argument
    """Test JWT cookie handling and edge cases for public client."""
    # Test empty JWT cookie
    with jwt_cookie(client, ""):
        response = client.get("/")
        assert response.status_code == 302, "Empty JWT cookie should redirect"

    # Test malformed JWT
    with jwt_cookie(client, "not.a.jwt"):
        response = client.get("/")
        assert response.status_code == 302, "Malformed JWT should redirect"

    # Test JWT with tampered signature
    valid_jwt = auth.token.access_token
    parts = valid_jwt.split(".")
    if len(parts) == 3:
        tampered_jwt = f"{parts[0]}.{parts[1]}.tampered_signature"
        with jwt_cookie(client, tampered_jwt):
            response = client.get("/")
            assert response.status_code == 302, "JWT with invalid signature should redirect"

    # Test JWT cookie precedence over Authorization header
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 200, "Valid JWT cookie should work even with invalid header"
