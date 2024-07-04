"""Conftest for kubernetes token-review tests"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kubernetes.service_account import ServiceAccount


@pytest.fixture(scope="module")
def create_service_account(request, cluster, blame, module_label):
    """Creates and returns service account"""

    def _create_service_account(name):
        service_account = ServiceAccount.create_instance(cluster, blame(name), labels={"app": module_label})
        request.addfinalizer(service_account.delete)
        service_account.commit()
        return service_account

    return _create_service_account


@pytest.fixture(scope="module")
def service_account_token(create_service_account, audience):
    """Create service account and request its bound token with the hostname as audience"""
    service_account = create_service_account("tkn-rev")
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth(service_account_token):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(service_account_token, "Bearer")
