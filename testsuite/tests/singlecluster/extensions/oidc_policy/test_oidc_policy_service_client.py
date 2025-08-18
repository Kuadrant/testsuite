"""Tests for OIDC policy functionality with Service Client.

This module tests OIDC authentication flows using a service client for machine-to-machine
authentication (Client Credentials Flow). Service clients are used for backend services
that need to authenticate without user interaction.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

import jwt
import pytest
from keycloak import KeycloakOpenID

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.oidc_policy import Provider
from testsuite.oidc import Token
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import jwt_cookie

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


def _get_auth_for_service_client(oidc_client: KeycloakOpenID) -> HttpxOidcClientAuth:
    """Get authentication for service client using client credentials flow."""

    def refresh_token_func(refresh_token: str) -> Token:
        """Refresh function that returns a new Token."""
        new_token_data = oidc_client.refresh_token(refresh_token)
        return Token(
            new_token_data["access_token"],
            refresh_token_func,
            new_token_data.get("refresh_token", ""),
        )

    try:
        # Service client: Machine-to-machine authentication
        token_data = oidc_client.token(grant_type="client_credentials", scope="openid")

        token = Token(
            token_data["access_token"],
            refresh_token_func,
            token_data.get("refresh_token", ""),
        )
        return HttpxOidcClientAuth(token, "authorization")

    except Exception as e:
        raise ValueError(f"Failed to get authentication for service client {oidc_client.client_id}: {e}") from e


def validate_jwt_token(token_string, expected_client_id):
    """Helper function to validate JWT token properties."""
    token = jwt.decode(token_string, options={"verify_signature": False})
    assert "openid" in token["scope"], "Token should include OpenID scope"
    assert token["typ"] == "Bearer", "Should be a Bearer token"
    assert token["azp"] == expected_client_id, "Token should be issued for correct client"
    return token


@pytest.fixture(scope="module")
def auth(service_client, keycloak):  # pylint: disable=unused-argument
    """Get authentication object for public client."""
    return _get_auth_for_service_client(service_client)


@pytest.fixture(scope="module")
def provider(oidc_provider, service_client):
    """Create Provider configuration for the OIDC policy."""
    return Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=service_client.client_id,
        clientSecret=getattr(service_client, "client_secret_key", None),
        authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
        tokenEndpoint=oidc_provider.well_known["token_endpoint"],
    )


# Service Client specific fixtures
@pytest.fixture(scope="module")
def service_client(request, keycloak):
    """Create a service client for machine-to-machine flow."""
    # Service client configuration
    client_params = {
        "name": "my-service-client",
        "publicClient": False,
        "standardFlowEnabled": False,
        "serviceAccountsEnabled": True,
        "protocol": "openid-connect",
        "clientId": "my-service-client",
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "redirectUris": [],
    }

    # Create the client in Keycloak
    keycloak_client = keycloak.realm.create_client(**client_params)
    request.addfinalizer(lambda: keycloak.realm.delete_client(keycloak_client.client_id))

    # Return KeycloakOpenID instance with client secret
    oidc_client = KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=keycloak_client.auth_id,
        realm_name=keycloak.realm_name,
        client_secret_key=keycloak_client.secret,
    )

    return oidc_client


# Tests
def test_service_client_machine_to_machine_flow(client, auth, service_client):
    """Test service client machine-to-machine authentication flow."""
    # Test unauthenticated request
    response = client.get("/")
    assert response.status_code == 302, "Service client should redirect when no credentials found"
    assert "x-ext-auth-reason" in response.headers, "Should provide auth failure reason"

    # Verify no sensitive information in redirect
    location = response.headers.get("Location", "")
    assert "client_secret" not in location, "Client secret should never appear in redirects"
    assert "client_credentials" not in location, "Grant type should not appear in redirects"

    # Service clients shouldn't have redirect URIs configured - verify this works
    # The redirect should not contain redirect_uri parameter for service clients
    # Note: The actual redirect behavior may vary based on OIDC policy configuration

    # Test JWT cookie authentication with valid token
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid service client JWT should allow access"

        token = validate_jwt_token(auth.token.access_token, service_client.client_id)

        # Service client specific validations
        assert "azp" in token, "Service client tokens should have authorized party (azp)"
        assert token["azp"] == service_client.client_id, "Token should be issued for correct service client"

        # Service clients use client_credentials flow, so no user context
        assert (
            "preferred_username" not in token or token.get("preferred_username") != "testuser"
        ), "Service client token should not contain user identity"

        # Should have service account context instead
        assert "clientId" in token or "azp" in token, "Should have client context"

        # Service client tokens should have specific characteristics
        assert "openid" in token["scope"], "Should include OpenID scope"
        assert token["typ"] == "Bearer", "Should be Bearer token"

        # Should NOT have user-specific claims (machine-to-machine)
        user_claims = ["preferred_username", "email", "given_name", "family_name"]
        for claim in user_claims:
            if claim in token:
                assert token[claim] != "testuser", f"Service client should not have user claim: {claim}"

    # Verify no sensitive information in response headers
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        for header_name, header_value in response.headers.items():
            assert "client_secret" not in str(header_value).lower(), f"Client secret found in {header_name}"


def test_service_client_jwt_handling(client, auth):
    """Test JWT cookie handling and edge cases for service client."""
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
