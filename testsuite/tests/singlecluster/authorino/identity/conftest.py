"""Conftest for all Identity tests"""

import pytest

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
def authorization(authorization):
    """For Identity tests remove all identities previously setup"""
    authorization.identity.clear_all()
    return authorization
