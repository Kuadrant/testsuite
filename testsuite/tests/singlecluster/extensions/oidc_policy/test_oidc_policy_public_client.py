"""Tests for OIDC policy functionality with Public Client.

This module tests OIDC authentication flows using a public client with PKCE
(Authorization Code Flow). Public clients are typically used in SPAs and mobile apps
where client secrets cannot be securely stored.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

from urllib.parse import quote

import pytest

from testsuite.oidc.test_client import OIDCTestClient

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


@pytest.fixture(scope="module")
def test_client(request, keycloak, hostname):
    """Create public OIDC test client"""
    client, keycloak_client = OIDCTestClient.create_public_client(keycloak, hostname.hostname)
    request.addfinalizer(lambda: keycloak.realm.delete_client(keycloak_client.client_id))
    return client


@pytest.fixture(scope="module")
def auth(test_client, keycloak):
    """Get authentication object for public client."""
    return test_client.get_auth(keycloak.test_username, keycloak.test_password)


@pytest.fixture(scope="module")
def provider(oidc_provider, test_client):
    """Create Provider configuration for the OIDC policy."""
    return test_client.create_provider_config(oidc_provider)


def test_public_client_authentication_flow(client, auth, test_client, gateway, jwt_helper):
    """Test complete public client authentication flow with PKCE."""
    # Test unauthenticated request redirects to OAuth2
    response = client.get("/")
    assert response.status_code == 302, "Unauthenticated request should redirect"
    assert "Location" in response.headers, "Redirect must include Location header"

    location = response.headers["Location"]

    # Validate OAuth2 redirect parameters
    assert "response_type=code" in location, "Should use Authorization Code Flow"
    assert "scope=openid" in location, "Should request OpenID scope"
    assert test_client.client_id in location, "Should include correct client ID"

    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location, "Should have correct redirect URI"

    # Public clients should use PKCE
    assert (
        "code_challenge" in location or "response_type=code" in location
    ), "Should use Authorization Code Flow with PKCE"

    # Verify no client_secret in redirect (public clients don't have secrets)
    assert "client_secret" not in location, "Public client should not expose client secret"

    # Test JWT cookie authentication with valid token
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid JWT cookie should allow access"

        token = test_client.validate_token(auth.token.access_token)

        # Public client specific token validations
        assert token["azp"] == test_client.client_id, "Token should be issued for correct public client"
        assert "preferred_username" in token, "Public client tokens should contain user identity"
        assert "email" in token, "Public client tokens should contain user email"
        assert token["preferred_username"] == "testuser", "Should be test user"
        assert token["email"] == "testuser@anything.invalid", "Token should contain user email"
        assert "openid" in token["scope"], "Token should include OpenID scope"

    # Test invalid JWT rejection
    jwt_helper.test_with_invalid_token("invalid.jwt.token")


def test_public_client_jwt_handling(auth, jwt_helper):
    """Test JWT cookie handling and edge cases for public client."""
    # Test JWT edge cases using helper methods
    jwt_helper.test_empty_cookie()
    jwt_helper.test_malformed_jwt()
    jwt_helper.test_tampered_signature(auth.token.access_token)

    # Test JWT cookie precedence over Authorization header
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = jwt_helper.client.get("/", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 200, "Valid JWT cookie should work even with invalid header"
