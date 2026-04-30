"""Shared fixtures for egress credential injection tests.

Provides MockServer backend and common infrastructure for all credential injection tests.
"""

import pytest

from testsuite.backend.mockserver import MockserverBackend
from testsuite.httpx import KuadrantClient
from testsuite.mockserver import Mockserver


@pytest.fixture(scope="module", autouse=True)
def cluster_ca_trust(kuadrant, skip_or_fail):
    """Skip tests if Authorino doesn't trust the cluster CA"""
    volumes = kuadrant.authorino.model.spec.get("volumes", {}).get("items", [])
    if not any(v.get("name") == "cluster-trust-bundle" for v in volumes):
        skip_or_fail("Authorino does not trust cluster CA (missing 'cluster-trust-bundle' volume)")


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label):
    """Deploy MockServer as the backend to validate injected credentials"""
    mockserver = MockserverBackend(cluster, blame("mocksrv"), label)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    return mockserver


@pytest.fixture(scope="module")
def mockserver_client(backend):
    """Mockserver client for creating expectations and direct requests"""
    return Mockserver(KuadrantClient(base_url=f"http://{backend.service.refresh().external_ip}:8080"))


@pytest.fixture(scope="module")
def rate_limit():
    """No rate limiting needed for credential injection tests"""
    return None
