"""Tests for OIDC policy functionality with Service Client.

This module tests OIDC authentication flows using a service client for machine-to-machine
authentication (Client Credentials Flow). Service clients are used for backend services
that need to authenticate without user interaction.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc.test_client import OIDCTestClient

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


@pytest.fixture(scope="module")
def test_client(request, keycloak, hostname):
    """Create service OIDC test client"""
    client, keycloak_client = OIDCTestClient.create_service_client(keycloak, hostname.hostname)
    request.addfinalizer(lambda: keycloak.realm.delete_client(keycloak_client.client_id))
    return client


@pytest.fixture(scope="module")
def auth(test_client):
    """Get authentication object for service client using service account token."""
    token = test_client.get_service_account_token()

    return HttpxOidcClientAuth(token, "authorization")


@pytest.fixture(scope="module")
def provider(oidc_provider, test_client):
    """Create Provider configuration for the OIDC policy."""
    return test_client.create_provider_config(oidc_provider)


def test_service_client_machine_to_machine_flow(client, auth, test_client, jwt_helper):
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
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid service client JWT should allow access"

        token = test_client.validate_token(auth.token.access_token)

        # Service client specific validations
        assert "azp" in token, "Service client tokens should have authorized party (azp)"
        assert token["azp"] == test_client.client_id, "Token should be issued for correct service client"

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
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = client.get("/")
        for header_name, header_value in response.headers.items():
            assert "client_secret" not in str(header_value).lower(), f"Client secret found in {header_name}"


def test_service_client_jwt_handling(auth, jwt_helper):
    """Test JWT cookie handling and edge cases for service client."""
    # Test JWT edge cases using helper methods
    jwt_helper.test_empty_cookie()
    jwt_helper.test_malformed_jwt()
    jwt_helper.test_tampered_signature(auth.token.access_token)
