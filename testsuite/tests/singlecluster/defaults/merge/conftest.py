"""Conftest for defaults merge strategy tests"""

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


@pytest.fixture(scope="module")
def create_api_key(blame, request, cluster):
    """Creates API key Secret"""

    def _create_secret(name, label_selector, api_key, ocp: KubernetesClient = cluster):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret
