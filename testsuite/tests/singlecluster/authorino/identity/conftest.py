"""Conftest for all Identity tests"""

import pytest

from testsuite.kubernetes.service_account import ServiceAccount
from testsuite.kuadrant.policy.authorization.auth_config import AuthConfig
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


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
def authorization(request, kuadrant, route, gateway, blame, cluster, label):  # pylint: disable=unused-argument
    """Create a fresh AuthConfig/AuthPolicy for the identity tests"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant is None:
        return AuthConfig.create_instance(cluster, blame("authz"), route, labels={"testRun": label})
    return AuthPolicy.create_instance(cluster, blame("authz"), target_ref, labels={"testRun": label})
