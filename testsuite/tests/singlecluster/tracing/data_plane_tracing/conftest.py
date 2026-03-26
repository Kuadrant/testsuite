"""Conftest for distributed tracing tests"""

import pytest


@pytest.fixture(scope="module", autouse=True)
def require_tracing_enabled(kuadrant, skip_or_fail):
    """Skip or fail tests if tracing is not configured in the Kuadrant CR"""
    tracing_spec = kuadrant.model.spec.get("observability", {}).get("tracing")
    if tracing_spec is None or tracing_spec.get("defaultEndpoint") is None:
        skip_or_fail("Tracing is not configured in Kuadrant CR")
