"""Tests for OIDCPolicy with custom redirectURI (kuadrant-operator#2032).

Validates that when provider.redirectURI is set, the OIDC redirect uses the custom
callback URL instead of the auto-constructed one from the gateway listener.
"""

from urllib.parse import unquote

import pytest

from keycloak import KeycloakOpenID

from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider
from testsuite.oidc.keycloak.objects import ClientConfig

pytestmark = [
    pytest.mark.authorino,
    pytest.mark.kuadrant_only,
    pytest.mark.extensions,
    pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2017"),
]

CUSTOM_CALLBACK_PATH = "/custom/callback"


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create confidential OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("custom-redir"),
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


@pytest.fixture(scope="module")
def custom_redirect_uri(gateway):
    """Custom redirect URI pointing to a non-default callback path."""
    gw_hostname = gateway.model.spec.listeners[0].hostname
    return f"http://{gw_hostname}{CUSTOM_CALLBACK_PATH}"


@pytest.fixture(scope="module")
def oidc_policy(cluster, blame, oidc_provider, keycloak_client, gateway, custom_redirect_uri):
    """OIDCPolicy with custom redirectURI set."""
    provider = Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=keycloak_client.client_id,
        authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
        tokenEndpoint=oidc_provider.well_known["token_endpoint"],
        redirectURI=custom_redirect_uri,
    )
    return OIDCPolicy.create_instance(cluster, blame("oidc-policy"), gateway, provider=provider)


def test_redirect_uses_custom_redirect_uri(client, custom_redirect_uri):
    """Initial redirect must use the custom redirectURI in the authorize URL."""
    response = client.get("/")
    assert response.status_code == 302

    location = unquote(response.headers["Location"])
    assert (
        f"redirect_uri={custom_redirect_uri}" in location
    ), f"Expected custom redirect_uri={custom_redirect_uri} in location, got: {location}"


def test_custom_callback_path_in_redirect_uri(client):
    """The redirect_uri parameter must contain the custom callback path, not the default /auth/callback."""
    response = client.get("/")
    assert response.status_code == 302

    location = unquote(response.headers["Location"])
    assert CUSTOM_CALLBACK_PATH in location, f"Custom callback path not found in: {location}"
    assert "/auth/callback" not in location or CUSTOM_CALLBACK_PATH in location
