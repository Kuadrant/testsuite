"""Conftest for tracing tests"""

import pytest

from testsuite.kubernetes.authorino import TracingOptions


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters, tracing):
    """Deploy authorino with tracing enabled"""
    authorino_parameters["tracing"] = TracingOptions(endpoint=tracing.collector_url, insecure=tracing.insecure)
    return authorino_parameters


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add response with 'request.id' to found traced request with it"""
    authorization.responses.add_simple("request.id")
    return authorization
