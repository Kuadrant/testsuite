"""Shared pytest fixtures for OIDC policy testing.

This module provides shared fixtures for testing OIDC (OpenID Connect) policy functionality,
including gateway setup and policy management. Client-specific fixtures are now located
in their respective test files.
"""

import pytest

from testsuite.gateway import Gateway, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy
from testsuite.oidc.cookie_helper import JWTCookieHelper


# Domain and Gateway fixtures
@pytest.fixture(scope="module")
def domain_name(blame):
    """Generate a unique domain name for testing."""
    return blame("hostname")


@pytest.fixture(scope="module")
def fully_qualified_domain_name(domain_name, base_domain):
    """Create a fully qualified domain name for testing."""
    return f"{domain_name}-kuadrant.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, fully_qualified_domain_name, cluster, blame, label) -> Gateway:
    """Create and configure the test Gateway."""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=fully_qualified_domain_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname(request, exposer, domain_name, gateway):
    """Create and expose a hostname for testing."""
    hostname = exposer.expose_hostname(domain_name, gateway)
    request.addfinalizer(hostname.delete)
    return hostname


# JWT Cookie Helper fixture
@pytest.fixture(scope="module")
def jwt_helper(client):
    """Create JWT cookie helper for testing"""
    return JWTCookieHelper(client)


# OIDC Policy fixtures - these are shared and will be overridden in individual test files
@pytest.fixture(scope="module")
def oidc_policy(cluster, blame, provider, gateway):
    """Create OIDC policy instance for testing.

    Note: This fixture depends on 'provider' which should be defined in each test file
    with the appropriate client-specific configuration.
    """
    oidc_policy = OIDCPolicy.create_instance(cluster, blame("oidc-policy"), gateway, provider=provider)
    return oidc_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, oidc_policy):
    """Commit and wait for OIDC policy to be ready."""
    request.addfinalizer(oidc_policy.delete)
    oidc_policy.commit()
    oidc_policy.wait_for_ready()
