"""Conftest for TokenRateLimitPolicy dataExtraction tests"""

import pytest

from testsuite.backend.mockserver import MockserverBackend
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy
from testsuite.mockserver import Mockserver

LIMIT = Limit(limit=25, window="20s")

# Providers covered by TokenRateLimitPolicy's built-in default totalTokens pointer list (RFC 0024),
# each isolated to its own limit/counter bucket via the x-mock-provider request header so the
# parametrized cases in test_default_pointers.py don't share rate-limit state.
DEFAULT_POINTER_PROVIDERS = ("openai", "gemini", "gemini-stream", "openai-responses-stream", "bedrock")


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label, backend_exposer):
    """Deploys a dedicated MockServer instance used to fabricate provider-accurate LLM responses"""
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


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for these tests"""
    return None


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """TokenRateLimitPolicy relying on the built-in default totalTokens pointer list (no
    dataExtraction set), with one limit per provider under test"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    for provider in DEFAULT_POINTER_PROVIDERS:
        policy.add_limit(
            name=f"{provider}-limit",
            limits=[LIMIT],
            when=[CelPredicate(predicate=f'request.headers["x-mock-provider"] == "{provider}"')],
        )
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, token_rate_limit):
    """Commits policies"""
    components = [c for c in [authorization, token_rate_limit] if c is not None]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
