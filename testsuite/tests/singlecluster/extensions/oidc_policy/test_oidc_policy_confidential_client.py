"""Tests for OIDC policy functionality with Confidential Client.

This module tests OIDC authentication flows using a confidential client with
Authorization Code Flow. Confidential clients can securely store client secrets
and are typically used in server-side web applications.

Key discovery: OIDC policy supports JWT token authentication via 'jwt' cookie,
allowing programmatic testing without full OAuth2 redirect flows.
"""

from urllib.parse import quote
import jwt as jwt_lib

import pytest

from testsuite.oidc.test_client import OIDCTestClient
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def test_client(keycloak, hostname):
    """Create confidential OIDC test client"""
    client = OIDCTestClient.create_confidential_client(keycloak, hostname.hostname)
    return client


@pytest.fixture(scope="module")
def auth(test_client, keycloak):
    """Get authentication object for confidential client."""
    return test_client.get_auth(keycloak.test_username, keycloak.test_password)


def test_confidential_client_authorization_flow(client, auth, test_client, gateway):
    """Test confidential client authorization code flow with secrets and enhanced features."""
    # Test unauthenticated request redirects
    response = client.get("/")
    assert response.status_code == 302, "Unauthenticated request should redirect"
    assert "Location" in response.headers, "Redirect must include Location header"

    location = response.headers["Location"]

    # Validate OAuth2 redirect parameters
    assert "response_type=code" in location, "Should use Authorization Code Flow"
    assert "scope=openid" in location, "Should request OpenID scope"
    assert test_client.oidc_client.client_id in location, "Should include correct client ID"

    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location, "Should have correct redirect URI"

    # Test JWT cookie authentication with valid token
    with set_jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200

        token = jwt_lib.decode(auth.token.access_token, options={"verify_signature": False})

        # Basic validations
        assert "openid" in token["scope"], "Token should include OpenID scope"
        assert token["typ"] == "Bearer", "Should be a Bearer token"
        assert (
            token["azp"] == test_client.oidc_client.client_id
        ), f"Token should be issued for {test_client.oidc_client.client_id}"

        # Confidential client specific token validations
        assert (
            token["azp"] == test_client.oidc_client.client_id
        ), "Token should be issued for correct confidential client"
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


def test_confidential_client_token(client, test_client, auth):
    """Test advanced confidential client features including refresh tokens and logout support."""
    with set_jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200

        # Test refresh token support
        assert hasattr(auth.token, "refresh_token"), "Should have refresh token"
        assert auth.token.refresh_token is not None, "Refresh token should not be None"
        assert hasattr(auth.token, "refresh_function"), "Should have refresh function"
        assert auth.token.refresh_function is not None, "Refresh function should not be None"

        token = jwt_lib.decode(auth.token.access_token, options={"verify_signature": False})

        # Basic validations
        assert "openid" in token["scope"], "Token should include OpenID scope"
        assert token["typ"] == "Bearer", "Should be a Bearer token"
        assert (
            token["azp"] == test_client.oidc_client.client_id
        ), f"Token should be issued for {test_client.oidc_client.client_id}"

        # Verify token properties that support logout scenarios (backchannel logout)
        assert "azp" in token, "Should have authorized party for logout tracking"
        assert "iat" in token, "Should have issued at time"
        assert "exp" in token, "Should have expiration time"


def test_confidential_client_malformed_jwt(client):
    """Test that malformed JWT is rejected and redirects to auth."""
    with set_jwt_cookie(client, "not.a.jwt"):
        response = client.get("/")
        assert response.status_code == 302, "Malformed JWT should redirect to authentication"


def test_confidential_client_tampered_jwt_signature(client, auth):
    """Test that JWT with tampered signature is rejected."""
    # Tamper with the signature part of a valid JWT
    parts = auth.token.access_token.split(".")
    if len(parts) != 3:
        pytest.fail("Invalid JWT token format")

    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature"
    with set_jwt_cookie(client, tampered_token):
        response = client.get("/")
        assert response.status_code == 302, "JWT with tampered signature should redirect to authentication"
