"""Tests for OIDC policy functionality with Confidential Client.

This module tests OIDC authentication flows using a confidential client with
Authorization Code Flow. Confidential clients can securely store client secrets
and are typically used in server-side web applications.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

from urllib.parse import quote

import pytest

from testsuite.oidc.test_client import OIDCTestClient

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


@pytest.fixture(scope="module")
def test_client(request, keycloak, hostname):
    """Create confidential OIDC test client"""
    client, keycloak_client = OIDCTestClient.create_confidential_client(keycloak, hostname.hostname)
    request.addfinalizer(lambda: keycloak.realm.delete_client(keycloak_client.client_id))
    return client


@pytest.fixture(scope="module")
def auth(test_client, keycloak):
    """Get authentication object for confidential client."""
    return test_client.get_auth(keycloak.test_username, keycloak.test_password)


@pytest.fixture(scope="module")
def provider(oidc_provider, test_client):
    """Create Provider configuration for the OIDC policy."""
    return test_client.create_provider_config(oidc_provider)


def test_confidential_client_authorization_flow(client, auth, test_client, gateway, jwt_helper):
    """Test confidential client authorization code flow with secrets and enhanced features."""
    # Test unauthenticated request redirects
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

    # Verify client secret is never exposed in redirects
    assert "client_secret" not in location, "Client secret should never appear in redirects"

    # Verify client has a secret (confidential clients should have secrets)
    assert test_client.client_secret is not None, "Client secret should not be None"

    # Test JWT cookie authentication with valid token
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid JWT cookie should allow access"

        token = test_client.validate_token(auth.token.access_token)

        # Confidential client specific token validations
        assert token["azp"] == test_client.client_id, "Token should be issued for correct confidential client"
        assert "preferred_username" in token, "Confidential client tokens should contain user identity"
        assert "email" in token, "Confidential client tokens should contain user email"
        assert token["preferred_username"] == "testuser", "Should be test user"
        assert token["email"] == "testuser@anything.invalid", "Token should contain user email"

        # Verify token contains expected scopes and enhanced claims
        assert "openid" in token["scope"], "Token should include OpenID scope"

        # May also have additional scopes like profile, email (configured in client setup)
        expected_claims = ["preferred_username", "email"]
        for claim in expected_claims:
            assert claim in token, f"Token should contain {claim} claim"


def test_confidential_client_advanced_features(auth, test_client, jwt_helper):
    """Test advanced confidential client features including refresh tokens and logout support."""
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        jwt_helper.test_with_valid_token(auth.token.access_token)

        # Test refresh token support
        assert hasattr(auth.token, "refresh_token"), "Should have refresh token"
        assert auth.token.refresh_token is not None, "Refresh token should not be None"
        assert hasattr(auth.token, "refresh_function"), "Should have refresh function"
        assert auth.token.refresh_function is not None, "Refresh function should not be None"

        token = test_client.validate_token(auth.token.access_token)

        # Verify token properties that support logout scenarios (backchannel logout)
        assert "azp" in token, "Should have authorized party for logout tracking"
        assert "iat" in token, "Should have issued at time"
        assert "exp" in token, "Should have expiration time"

    # Test JWT edge cases using helper methods
    jwt_helper.test_empty_cookie()
    jwt_helper.test_malformed_jwt()
    jwt_helper.test_tampered_signature(auth.token.access_token)

    # Test JWT cookie precedence over Authorization header
    with jwt_helper.set_jwt_cookie(auth.token.access_token):
        response = jwt_helper.client.get("/", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 200, "Valid JWT cookie should work even with invalid header"
