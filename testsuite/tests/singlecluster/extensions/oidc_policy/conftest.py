"""Shared pytest fixtures for OIDC policy testing.

This module provides shared fixtures for testing OIDC (OpenID Connect) policy functionality,
including gateway setup and policy management. Client-specific fixtures are now located
in their respective test files.
"""

from contextlib import contextmanager
import pytest

from testsuite.gateway import Gateway, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.metrics_gateway import MetricsServiceGateway
from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy
from testsuite.kubernetes.service import ServicePort


@pytest.fixture(scope="module")
def gateway(request, domain_name, base_domain, cluster, blame, label) -> Gateway:
    """Create and configure the test Gateway."""
    fqdn = f"{domain_name}-kuadrant.{base_domain}"
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=fqdn))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway_metrics_service(request, gateway, cluster, blame, label, exposer):  # pylint: disable=unused-argument
    """Create OpenShift Route to expose gateway metrics, bypassing Gateway/OIDC."""
    # Create OpenShift Route directly to metrics service (bypasses Gateway and OIDC)
    metrics_service = MetricsServiceGateway.create_instance(
        cluster,
        blame("metrics"),
        selector={"gateway.networking.k8s.io/gateway-name": gateway.name()},
        ports=[ServicePort(name="api", port=15020, targetPort=15020)],
        labels={"app": label},
        service_type="LoadBalancer",
    )

    metrics_service.commit()
    metrics_service.wait_for_ready()

    return exposer.expose_hostname(blame("metrics"), metrics_service)


# JWT Cookie Helper fixture
@contextmanager
def set_jwt_cookie(client, token_value: str):
    """Context manager for setting JWT cookies with automatic cleanup"""
    client.cookies.set("jwt", token_value)
    try:
        yield
    finally:
        client.cookies.clear()


# OIDC Policy fixtures - these are shared and will be overridden in individual test files
@pytest.fixture(scope="module")
def oidc_policy_provider_config(oidc_provider, test_client):
    """Create Provider configuration for the OIDC policy."""
    return test_client.create_provider_config(oidc_provider)


@pytest.fixture(scope="module")
def oidc_policy(cluster, blame, oidc_policy_provider_config, gateway, gateway_metrics_service):
    """Create OIDC policy instance for testing.

    Note: This fixture depends on 'provider' which should be defined in each test file
    with the appropriate client-specific configuration.
    """
    policy = OIDCPolicy.create_instance(cluster, blame("oidc-policy"), gateway, provider=oidc_policy_provider_config)
    policy.set_gateway_metrics_service(gateway_metrics_service)
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, oidc_policy):  # pylint: disable=unused-argument
    """Commit and wait for OIDC policy to be ready (including Envoy application).

    Depends on route to ensure proper ordering: route must exist before policy is applied.
    """
    request.addfinalizer(oidc_policy.delete)
    oidc_policy.commit()
    oidc_policy.wait_for_ready()
