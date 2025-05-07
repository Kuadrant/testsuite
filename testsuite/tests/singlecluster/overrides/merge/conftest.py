"""Conftest for overrides merge strategy tests"""

import pytest

from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient


def create_secret(name, label_selector, api_key, ocp: KubernetesClient, annotations=None):
    """Creates a secret to be used as an api key"""
    secret_name = name
    secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key, annotations)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def route(route, backend):
    """Add 2 backend rules for specific backend paths"""
    route.remove_all_rules()
    route.add_backend(backend, "/get")
    route.add_backend(backend, "/anything")
    return route
