"""Conftest for overrides merge strategy tests"""

import pytest

from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient


@pytest.fixture(scope="module")
def route(route, backend):
    """Add 2 backend rules for specific backend paths"""
    route.remove_all_rules()
    route.add_backend(backend, "/get")
    route.add_backend(backend, "/anything")
    return route
