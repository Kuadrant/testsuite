"""Conftest for overrides merge strategy tests"""

import pytest


@pytest.fixture(scope="module")
def route(route, backend):
    """Add 2 backend rules for specific backend paths"""
    route.remove_all_rules()
    route.add_backend(backend, "/get")
    route.add_backend(backend, "/anything")
    return route
