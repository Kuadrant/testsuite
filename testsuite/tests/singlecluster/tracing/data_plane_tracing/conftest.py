"""Conftest for distributed tracing tests"""

import pytest

from testsuite.gateway.gateway_api.gateway import KuadrantGateway


@pytest.fixture(scope="session")
def has_ocp_managed_istio(cluster):
    """True if the cluster uses 'openshift-default' GatewayClass (OCP-managed Istio)"""
    return KuadrantGateway.get_gateway_class_name(cluster) == "openshift-default"


@pytest.fixture(scope="module", autouse=True)
def require_tracing_enabled(kuadrant, skip_or_fail):
    """Skip or fail tests if tracing is not configured in the Kuadrant CR"""
    tracing_spec = kuadrant.model.spec.get("observability", {}).get("tracing")
    if tracing_spec is None or tracing_spec.get("defaultEndpoint") is None:
        skip_or_fail("Tracing is not configured in Kuadrant CR")
