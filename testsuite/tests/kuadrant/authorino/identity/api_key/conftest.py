"""Conftest for authorino API key identity"""

import pytest

from testsuite.openshift.objects.api_key import APIKey


@pytest.fixture(scope="module")
def create_api_key(blame, request, openshift):
    """Creates API key Secret"""
    def _create_secret(name, label_selector, api_key):
        secret_name = blame(name)
        secret = APIKey.create_instance(openshift, secret_name, label_selector, api_key)
        request.addfinalizer(secret.delete)
        secret.commit()
        return secret_name
    return _create_secret
