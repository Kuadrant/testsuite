import pytest

from keycloak import KeycloakOpenID
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider
from testsuite.oidc import Token


@pytest.fixture(scope="module")
def public_client(keycloak):
    """Creates a public client with Authorization Code Flow + PKCE enabled"""
    client = keycloak.realm.create_client(
        name="my-public-client",
        publicClient=True,  # This makes it a public client (no client authentication)
        standardFlowEnabled=True,  # Enables Authorization Code Flow
        directAccessGrantsEnabled=True,  # Enables Resource Owner Password Credentials
        serviceAccountsEnabled=False,  # Public clients don't use service accounts
        authorizationServicesEnabled=False,  # No need for authorization services
        # PKCE is enabled by default for public clients in Keycloak
    )
    # For public clients, we create the OIDC client without a client secret
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        realm_name=keycloak.realm_name  # No client_secret_key for public clients
    )


@pytest.fixture(scope="module")
def provider(oidc_provider):
    return Provider(
        issuer_url=oidc_provider.well_known["issuer"],
        client_id="my-public-client",
        # authorization_endpoint=oidc_provider.well_known["authorization_endpoint"],
        # token_endpoint=oidc_provider.well_known["token_endpoint"],
    )


@pytest.fixture(scope="module")
def auth(public_client, keycloak):
    """Returns authentication object for HTTPX"""
    token_data = public_client.token(keycloak.test_username, keycloak.test_password)
    token = Token(
        token_data["access_token"],
        public_client.refresh_token,
        token_data["refresh_token"]
    )
    return HttpxOidcClientAuth(token, "authorization")


@pytest.fixture(scope="module")
def oidc_policy(request, cluster, blame, route, provider):
    oidc_policy = OIDCPolicy.create_instance(cluster, blame("oidc-policy"), route, provider=provider)
    request.addfinalizer(oidc_policy.delete)
    oidc_policy.commit()
    return oidc_policy