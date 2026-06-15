"""Shared pytest fixtures for OIDC policy testing."""

from contextlib import contextmanager

import pytest

from testsuite.gateway import Gateway, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider

@pytest.fixture(scope="module")
def gateway(request, domain_name, base_domain, cluster, blame, label) -> Gateway:
    """Create and configure the test Gateway."""
    fqdn = f"{domain_name}-{cluster.project}.{base_domain}"
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=fqdn))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@contextmanager
def set_jwt_cookie(client, token_value: str):
    """Context manager for setting JWT cookies with automatic cleanup."""
    client.cookies.set("jwt", token_value)
    try:
        yield
    finally:
        client.cookies.clear()


@pytest.fixture(scope="module")
def oidc_policy_provider_config(oidc_provider, keycloak_client):
    """Create Provider configuration for the OIDC policy."""
    return Provider(
        issuerURL=oidc_provider.well_known["issuer"],
        clientID=keycloak_client.client_id,
        authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
        tokenEndpoint=oidc_provider.well_known["token_endpoint"],
    )


@pytest.fixture(scope="module")
def oidc_policy(cluster, blame, oidc_policy_provider_config, gateway):
    """Create OIDC policy instance targeting the gateway."""
    return OIDCPolicy.create_instance(cluster, blame("oidc-policy"), gateway, provider=oidc_policy_provider_config)


@pytest.fixture(scope="module", autouse=True)
def commit(request, oidc_policy):
    """Commit and wait for OIDC policy to be ready."""
    request.addfinalizer(oidc_policy.delete)
    oidc_policy.commit()
    oidc_policy.wait_for_ready()
