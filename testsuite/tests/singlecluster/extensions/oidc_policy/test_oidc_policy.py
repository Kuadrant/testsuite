"""Tests for OIDC policy functionality in Kuadrant.

This module tests different OIDC authentication flows:
- Public client with PKCE
- Service client (machine-to-machine)
- Confidential client with authorization code
"""

from urllib.parse import quote

import jwt
import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]


@pytest.mark.parametrize("oidc_policy", ["gateway", "route"], indirect=True)
@pytest.mark.parametrize("gateway", ["fully_qualified_domain_name", "wildcard_domain"], indirect=True)
@pytest.mark.parametrize("oidc_client", ["public_client"], indirect=True)
def test_public_client_flow(client, auth, oidc_client, gateway):
    """Test public client with PKCE flow"""
    # No auth -> redirect to login with PKCE
    response = client.get("/")
    assert response.status_code == 302
    assert "Location" in response.headers
    location = response.headers["Location"]
    assert "response_type=code" in location  # Uses authorization  code flow
    assert "scope=openid" in location  # Requests OpenID scope
    assert oidc_client.client_id in location  # Correct client ID in redirect
    assert (
        f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}" in location
    )  # Correct redirect URI

    # Valid auth -> success with correct token
    response = client.get("/", auth=auth)
    assert response.status_code == 200
    token = jwt.decode(auth.token.access_token, options={"verify_signature": False})
    assert "openid" in token["scope"]  # Has OpenID scope
    assert token["typ"] == "Bearer"  # Correct token type


@pytest.mark.parametrize("oidc_policy", ["gateway", "route"], indirect=True)
@pytest.mark.parametrize("gateway", ["fully_qualified_domain_name", "wildcard_domain"], indirect=True)
@pytest.mark.parametrize("oidc_client", ["service_client"], indirect=True)
def test_service_client_flow(client, auth, oidc_client):
    """Test service client (machine-to-machine) flow"""
    # No auth -> redirect with auth error
    response = client.get("/")
    assert response.status_code == 302
    assert "x-ext-auth-reason" in response.headers
    assert response.headers["x-ext-auth-reason"] == "credential not found"
    location = response.headers["Location"]
    assert "client_secret" not in location  # No sensitive info in redirect

    # Valid auth -> success with correct token
    response = client.get("/", auth=auth)
    assert response.status_code == 200
    token = jwt.decode(auth.token.access_token, options={"verify_signature": False})
    assert "openid" in token["scope"]  # Has OpenID scope
    assert token["azp"] == oidc_client.client_id  # Correct client ID


@pytest.mark.parametrize("oidc_policy", ["gateway", "route"], indirect=True)
@pytest.mark.parametrize("gateway", ["fully_qualified_domain_name", "wildcard_domain"], indirect=True)
@pytest.mark.parametrize("oidc_client", ["confidential_client"], indirect=True)
def test_confidential_client_flow(client, auth, oidc_client, gateway):
    """Test confidential client with auth code flow"""
    # No auth -> redirect to login
    response = client.get("/")
    assert response.status_code == 302
    assert "Location" in response.headers
    location = response.headers["Location"]
    assert "response_type=code" in location  # Uses authorization code flow
    assert "scope=openid" in location  # Requests OpenID scope
    assert oidc_client.client_id in location  # Correct client ID in redirect
    assert (
        f"redirect_uri=http%3A%2F%2F{quote(gateway.model.spec.listeners[0].hostname, safe=':.')}" in location
    )  # Correct redirect URI

    # Valid auth -> success with correct token
    response = client.get("/", auth=auth)
    assert response.status_code == 200
    token = jwt.decode(auth.token.access_token, options={"verify_signature": False})
    assert "openid" in token["scope"]  # Has OpenID scope
    assert token["typ"] == "Bearer"  # Correct token type
