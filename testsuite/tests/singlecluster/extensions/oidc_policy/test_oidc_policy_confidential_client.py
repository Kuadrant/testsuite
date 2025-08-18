"""Tests for OIDC policy functionality with Confidential Client.

This module tests OIDC authentication flows using a confidential client with
Authorization Code Flow. Confidential clients can securely store client secrets
and are typically used in server-side web applications.

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


def _get_auth_for_confidential_client(oidc_client: KeycloakOpenID, keycloak) -> HttpxOidcClientAuth:
    """Get authentication for confidential client using user credentials."""

    def refresh_token_func(refresh_token: str) -> Token:
        """Refresh function that returns a new Token."""
        new_token_data = oidc_client.refresh_token(refresh_token)
        return Token(
            new_token_data["access_token"],
            refresh_token_func,
            new_token_data.get("refresh_token", ""),
        )

    try:
        # Confidential client: User authentication
        token_data = oidc_client.token(keycloak.test_username, keycloak.test_password)

        token = Token(
            token_data["access_token"],
            refresh_token_func,
            token_data.get("refresh_token", ""),
        )
        return HttpxOidcClientAuth(token, "authorization")

    except Exception as e:
        raise ValueError(f"Failed to get authentication for confidential client {oidc_client.client_id}: {e}") from e


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


# Confidential Client specific fixtures
@pytest.fixture(scope="module")
def confidential_client(request, keycloak, hostname):
    """Create a confidential client with Authorization Code Flow."""
    # Confidential client configuration
    client_params = {
        "name": "my-confidential-client",
        "publicClient": False,
        "standardFlowEnabled": True,
        "serviceAccountsEnabled": True,
        "protocol": "openid-connect",
        "clientId": "my-confidential-client",
        "redirectUris": [f"http://{hostname.hostname}/*"],
        "webOrigins": [f"http://{hostname.hostname}"],
        "directAccessGrantsEnabled": True,
        "rootUrl": f"http://{hostname.hostname}",
        "defaultClientScopes": ["openid", "profile", "email"],
        "optionalClientScopes": ["offline_access", "microprofile-jwt"],
        "attributes": {
            "backchannel.logout.session.required": "true",
            "use.refresh.tokens": "true",
        },
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


@pytest.fixture(scope="module")
def auth(confidential_client, keycloak):
    """Get authentication object for confidential client."""
    return _get_auth_for_confidential_client(confidential_client, keycloak)


@pytest.fixture(scope="module")
def provider(oidc_provider, confidential_client):
    """Create Provider configuration for the OIDC policy."""
    return Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=confidential_client.client_id,
        clientSecret=getattr(confidential_client, "client_secret_key", None),
        authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
        tokenEndpoint=oidc_provider.well_known["token_endpoint"],
    )


# Tests
def test_confidential_client_authorization_flow(client, auth, confidential_client, gateway):
    """Test confidential client authorization code flow with secrets and enhanced features."""
    # Test unauthenticated request redirects
    response = client.get("/")
    assert response.status_code == 302, "Unauthenticated request should redirect"
    assert "Location" in response.headers, "Redirect must include Location header"

    location = response.headers["Location"]

    # Validate OAuth2 redirect parameters
    validate_oauth2_redirect(location, confidential_client, gateway)

    # Confidential clients should use Authorization Code Flow
    assert "response_type=code" in location, "Should use Authorization Code Flow"
    assert "scope=openid" in location, "Should request OpenID scope"
    assert confidential_client.client_id in location, "Should include correct client ID"

    # Should have proper redirect URI
    expected_redirect_uri = f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}"
    assert expected_redirect_uri in location, "Should have correct redirect URI"

    # Verify client secret is never exposed in redirects
    assert "client_secret" not in location, "Client secret should never appear in redirects"

    # Verify client has a secret (confidential clients should have secrets)
    assert hasattr(confidential_client, "client_secret_key"), "Confidential client should have a secret"
    assert confidential_client.client_secret_key is not None, "Client secret should not be None"

    # Test JWT cookie authentication with valid token
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid JWT cookie should allow access"

        token = validate_jwt_token(auth.token.access_token, confidential_client.client_id)

        # Confidential client specific token validations
        assert token["azp"] == confidential_client.client_id, "Token should be issued for correct confidential client"
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


def test_confidential_client_advanced_features(client, auth, confidential_client):
    """Test advanced confidential client features including refresh tokens and logout support."""
    with jwt_cookie(client, auth.token.access_token):
        response = client.get("/")
        assert response.status_code == 200, "Valid JWT cookie should allow access"

        # Test refresh token support
        assert hasattr(auth.token, "refresh_token"), "Should have refresh token"
        assert auth.token.refresh_token is not None, "Refresh token should not be None"
        assert hasattr(auth.token, "refresh_function"), "Should have refresh function"
        assert auth.token.refresh_function is not None, "Refresh function should not be None"

        token = validate_jwt_token(auth.token.access_token, confidential_client.client_id)

        # Verify token properties that support logout scenarios (backchannel logout)
        assert "azp" in token, "Should have authorized party for logout tracking"
        assert "iat" in token, "Should have issued at time"
        assert "exp" in token, "Should have expiration time"

    # Test JWT edge cases
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
