"""Shared fixtures for egress credential injection tests.

Provides MockServer backend and common infrastructure for all credential injection tests.
"""

import pytest

from testsuite.backend.mockserver import MockserverBackend
from testsuite.mockserver import Mockserver


@pytest.fixture(scope="module", autouse=True)
def cluster_ca_trust(kuadrant, skip_or_fail):
    """Skip tests if Authorino doesn't trust the cluster CA"""
    volumes = kuadrant.authorino.model.spec.get("volumes", {}).get("items", [])
    if not any(v.get("name") == "cluster-trust-bundle" for v in volumes):
        skip_or_fail("Authorino does not trust cluster CA (missing 'cluster-trust-bundle' volume)")


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label, backend_exposer):
    """Deploy MockServer as the backend to validate injected credentials"""
    mockserver = MockserverBackend(cluster, blame("mocksrv"), label, service_type=backend_exposer.backend_service_type)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    mockserver.expose(backend_exposer, blame("mocksrv"))
    return mockserver


@pytest.fixture(scope="module")
def mockserver_client(backend):
    """Mockserver client for creating expectations and direct requests"""
    return Mockserver(backend.admin_hostname.client())


@pytest.fixture(scope="module")
def rate_limit():
    """No rate limiting needed for credential injection tests"""
    return None
