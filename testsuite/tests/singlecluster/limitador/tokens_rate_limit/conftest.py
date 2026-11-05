"""Conftest for TokenRateLimitPolicy tests"""

import pytest

from testsuite.backend.mockserver import MockserverBackend
from testsuite.mockserver import Mockserver


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label, backend_exposer):
    """Deploys a dedicated MockServer instance used to fabricate LLM-shaped responses"""
    mockserver = MockserverBackend(cluster, blame("mocksrv"), label, service_type=backend_exposer.backend_service_type)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    mockserver.expose(backend_exposer, blame("mocksrv"))
    return mockserver


@pytest.fixture(scope="module")
def mockserver_client(backend):
    """Mockserver client for creating LLM response expectations"""
    return Mockserver(backend.admin_hostname.client())


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, token_rate_limit):
    """Commits policies"""
    components = [c for c in [authorization, token_rate_limit] if c is not None]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
