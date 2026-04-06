"""Conftest for distributed tracing tests"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    annotations = {"user": "testuser"}
    return create_api_key("api-key", module_label, "IAMTESTUSER", annotations=annotations)


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Configures authorization policy with API key identity and user extraction."""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "user": ValueFrom("auth.identity.metadata.annotations.user"),
            }
        ),
    )
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Configures rate limit policy with CEL-based user targeting."""
    rate_limit.add_limit("testuser", [Limit(3, "10s")], when=[CelPredicate("auth.identity.user == 'testuser'")])
    return rate_limit
