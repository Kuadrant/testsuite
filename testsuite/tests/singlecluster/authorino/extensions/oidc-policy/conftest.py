import pytest

from keycloak import KeycloakOpenID
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider
from testsuite.oidc import Token

@pytest.fixture(scope="module")
def exact_hostname(hostname):
    """Exposed Hostname object"""
    return hostname.hostname


@pytest.fixture(scope="module")
def no_hostname():
    """No hostname"""
    return None


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, label):
    """Returns the test target(gateway or route)"""
    hostname = request.getfixturevalue(getattr(request, "param", "wildcard_domain"))

    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=hostname))
    return gw

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
def service_client(keycloak):
    """Creates a confidential client for service account (machine-to-machine) flow"""
    client = keycloak.realm.create_client(
        name="my-service-client",
        publicClient=False,  # This makes it a confidential client (requires client authentication)
        standardFlowEnabled=False,  # Disable Authorization Code Flow
        implicitFlowEnabled=False,  # Disable Implicit Flow
        directAccessGrantsEnabled=False,  # Disable Direct Access Grants
        serviceAccountsEnabled=True,  # Enable service account for client credentials flow
        authorizationServicesEnabled=False,  # No need for authorization services
    )
    
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        client_secret_key=client.secret,
        realm_name=keycloak.realm_name
    )

@pytest.fixture(scope="module")
def confidential_client(keycloak):
    """Creates a confidential client with Authorization Code Flow enabled"""
    client = keycloak.realm.create_client(
        name="my-confidential-client",
        publicClient=False,  # This makes it a confidential client (requires client authentication)
        standardFlowEnabled=True,  # Enables Authorization Code Flow
        directAccessGrantsEnabled=True,  # Enables Resource Owner Password Credentials
        serviceAccountsEnabled=True,  # Enable service account for confidential client
        authorizationServicesEnabled=False,  # No need for authorization services
        # rootUrl="http://localhost:8080",  # Root URL as specified
        # redirectUris=["http://localhost:8080/*"],  # Redirect URIs as specified
    )
    
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=client.auth_id,
        client_secret_key=client.secret,
        realm_name=keycloak.realm_name
    )


@pytest.fixture(scope="module")
def oidc_client(request) -> KeycloakOpenID:
    """Fixture which enables switching out OIDC clients for individual modules"""
    return request.getfixturevalue(request.param)

@pytest.fixture(scope="module")
def provider(oidc_provider, oidc_client):   
    """Returns a Provider instance configured for the specified client type"""
    return Provider(
        issuer_url=oidc_provider.well_known["issuer"],
        client_id=oidc_client.client_id,
        client_secret=oidc_client.client_secret_key,
    )


@pytest.fixture(scope="module")
def auth(oidc_client, keycloak):
    """Returns authentication object for HTTPX"""
    if isinstance(oidc_client, KeycloakOpenID) and hasattr(oidc_client, 'client_id') and oidc_client.client_id == "my-service-client":
        # For service client, use client credentials grant
        token_data = oidc_client.token(grant_type=["client_credentials"], scope="openid")
    else:
        # For other clients, use password grant (simulating Authorization Code flow)
        token_data = oidc_client.token(keycloak.test_username, keycloak.test_password)
    
    token = Token(
        token_data["access_token"],
        oidc_client.refresh_token,
        token_data.get("refresh_token")  # Client credentials doesn't return refresh token
    )
    return HttpxOidcClientAuth(token, "authorization")


@pytest.fixture(scope="module")
def oidc_policy(request, cluster, blame, gateway, provider):
    oidc_policy = OIDCPolicy.create_instance(cluster, blame("oidc-policy"), gateway, provider=provider)
    request.addfinalizer(oidc_policy.delete)
    return oidc_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, gateway, oidc_policy):
    """Commits all important stuff before tests"""
    for component in [gateway,oidc_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()