"""Conftest for tracing tests"""

import pytest

from testsuite.openshift.authorino import TracingOptions


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters, tracing):
    """Deploy authorino with tracing enabled"""
    insecure_tracing = not tracing.client.verify
    authorino_parameters["tracing"] = TracingOptions(endpoint=tracing.collector_url, insecure=insecure_tracing)
    return authorino_parameters


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add response with 'request.id' to found traced request with it"""
    authorization.responses.add_simple("request.id")
    return authorization
