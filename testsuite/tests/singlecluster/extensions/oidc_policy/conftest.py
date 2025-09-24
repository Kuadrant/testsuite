"""Pytest fixtures for OIDC policy testing.

This module provides fixtures for testing OIDC (OpenID Connect) policy functionality,
including various client configurations (public, confidential, and service clients),
gateway setup, and policy management."""

import pytest
from keycloak import KeycloakOpenID

from testsuite.gateway import Gateway, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider, Auth, Credentials, Prefixed
from testsuite.oidc import Token


@pytest.fixture(scope="module")
def domain_name(blame):
    """Generate a unique domain name for testing."""
    return blame("hostname")


@pytest.fixture(scope="module")
def fully_qualified_domain_name(domain_name, base_domain):
    """Create a fully qualified domain name for testing."""
    return f"{domain_name}-kuadrant.{base_domain}"


@pytest.fixture(scope="module")
def wildcard_domain(base_domain):
    """Create a wildcard domain for testing."""
    return f"*.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, label) -> Gateway:
    """Returns the test Gateway with parametrized hostname"""
    # Map parameter values to actual hostnames
    hostname = request.getfixturevalue(getattr(request, "param", "wildcard_domain"))

    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=hostname))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname(
    request,
    exposer,
    domain_name,
    gateway,
):
    """Create and expose a hostname for testing."""
    hostname = exposer.expose_hostname(domain_name, gateway)
    request.addfinalizer(hostname.delete)
    return hostname


@pytest.fixture(scope="module")
def public_client(request, keycloak, hostname):
    """Creates a public client with Authorization Code Flow + PKCE enabled"""
    client_name = "my-public-client"
    client = keycloak.realm.create_client(
        name=client_name,
        publicClient=True,  # This makes it a public client (no client authentication)
        standardFlowEnabled=True,  # Enables Authorization Code Flow
        protocol="openid-connect",
        redirectUris=[f"http://{hostname.hostname}/*"],  # Allow all paths for testing
        webOrigins=[f"http://{hostname.hostname}"],  # Allow CORS from our domain
    )

    request.addfinalizer(lambda: keycloak.realm.delete_client(client.client_id))

    # For public clients, we create the OIDC client without a client secret
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        realm_name=keycloak.realm_name,  # No client_secret_key for public clients
    )


@pytest.fixture(scope="module")
def service_client(request, keycloak):
    """Creates a confidential client for service account (machine-to-machine) flow"""
    client_name = "my-service-client"
    client = keycloak.realm.create_client(
        name=client_name,
        publicClient=False,  # This makes it a confidential client
        standardFlowEnabled=False,  # Disable Authorization Code Flow
        implicitFlowEnabled=False,  # Disable Implicit Flow
        directAccessGrantsEnabled=False,  # Disable Direct Access Grants
        serviceAccountsEnabled=True,  # Enable service account for client credentials flow
        protocol="openid-connect",
        clientId=client_name,  # Used as audience in tokens
        # Service clients should not have any redirect URIs since they only use client credentials
        redirectUris=[],
    )

    request.addfinalizer(lambda: keycloak.realm.delete_client(client.client_id))

    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        client_secret_key=client.secret,
        realm_name=keycloak.realm_name,
    )


@pytest.fixture(scope="module")
def confidential_client(request, keycloak, hostname):
    """Creates a confidential client with Authorization Code Flow enabled"""
    client_name = "my-confidential-client"
    client = keycloak.realm.create_client(
        name=client_name,
        publicClient=False,  # This makes it a confidential client (requires client authentication)
        standardFlowEnabled=True,  # Enables Authorization Code Flow
        directAccessGrantsEnabled=True,  # Enables Resource Owner Password Credentials
        serviceAccountsEnabled=True,  # Enable service account for confidential client
        authorizationServicesEnabled=False,  # No need for authorization services
        redirectUris=[
            f"http://{hostname.hostname}/auth/callback",
            f"http://{hostname.hostname}/*",  # Allow all paths for testing
        ],
        webOrigins=[f"http://{hostname.hostname}"],  # Allow CORS from our domain
        rootUrl=f"http://{hostname.hostname}",  # Set the root URL for the client
        attributes={
            "backchannel.logout.session.required": "true",
            "backchannel.logout.revoke.offline.tokens": "false",
            "use.refresh.tokens": "true",
            "client_credentials.use_refresh_token": "false",
        },
        protocol="openid-connect",
        defaultClientScopes=["openid", "profile", "email"],
        optionalClientScopes=["offline_access", "microprofile-jwt"],
        clientId=client_name,  # Used as audience in tokens
    )

    request.addfinalizer(lambda: keycloak.realm.delete_client(client.client_id))

    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        client_secret_key=client.secret,
        realm_name=keycloak.realm_name,
    )


@pytest.fixture(scope="module")
def oidc_client(request) -> KeycloakOpenID:
    """Fixture which enables switching out OIDC clients for individual modules"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def provider(oidc_provider, oidc_client):
    """Returns a Provider instance configured for the specified client type"""
    return Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=oidc_client.client_id,
        clientSecret=oidc_client.client_secret_key,
        authorizationEndpoint=f"{oidc_provider.well_known['authorization_endpoint']}",
        tokenEndpoint=f"{oidc_provider.well_known['token_endpoint']}",
    )


@pytest.fixture(scope="module")
def auth(oidc_client, keycloak):
    """Returns authentication object for HTTPX"""
    if (
        isinstance(oidc_client, KeycloakOpenID)
        and hasattr(oidc_client, "client_id")
        and oidc_client.client_id == "my-service-client"
    ):
        # For service client, use client credentials grant
        token_data = oidc_client.token(grant_type=["client_credentials"], scope="openid")
    else:
        # For other clients, use password grant (simulating Authorization Code flow)
        token_data = oidc_client.token(keycloak.test_username, keycloak.test_password)

    token = Token(
        token_data["access_token"],
        oidc_client.refresh_token,
        token_data.get("refresh_token"),  # Client credentials doesn't return refresh token
    )
    return HttpxOidcClientAuth(token, "authorization")


@pytest.fixture(scope="module")
def oidc_policy(request, cluster, blame, provider):
    """Create an OIDC policy instance for testing."""
    # Create auth configuration to tell where to look for the token
    target_ref = request.getfixturevalue(getattr(request, "param", "gateway"))

    credentials = Credentials(authorizationHeader=Prefixed(prefix="Bearer"))
    auth = Auth(tokenSource=credentials)

    oidc_policy = OIDCPolicy.create_instance(cluster, blame("oidc-policy"), target_ref, provider=provider, auth=auth)
    request.addfinalizer(oidc_policy.delete)
    return oidc_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, oidc_policy):
    """Commits all important stuff before tests"""
    request.addfinalizer(oidc_policy.delete)
    oidc_policy.commit()
    oidc_policy.wait_for_ready()
