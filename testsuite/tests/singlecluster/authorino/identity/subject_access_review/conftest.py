"""Conftest for SubjectAccessReview related tests."""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kubernetes.cluster_role import ClusterRoleBinding


@pytest.fixture(scope="module")
def audience(hostname):
    """Return hostname as only audience for the service account bound token"""
    return [hostname.hostname]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes token-review and subject-access-review identity"""
    authorization.identity.add_kubernetes("token-review-host")
    return authorization


@pytest.fixture(scope="module")
def create_cluster_role_binding(request, cluster, blame, module_label):
    """Creates and returns a ClusterRoleBinding"""

    def _create_cluster_role_binding(cluster_role, service_accounts):
        cluster_role_binding = ClusterRoleBinding.create_instance(
            cluster, blame("crb"), cluster_role, service_accounts, labels={"app": module_label}
        )
        request.addfinalizer(cluster_role_binding.delete)
        cluster_role_binding.commit()
        return cluster_role_binding

    return _create_cluster_role_binding


@pytest.fixture(scope="module")
def service_account_token(create_service_account, create_cluster_role_binding, cluster_role, audience):
    """Create a ServiceAccount, bind it to a ClusterRole and return its token with a given audience"""
    service_account = create_service_account("auth")
    create_cluster_role_binding(cluster_role.name(), [service_account.name()])
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth(service_account_token):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(service_account_token, "Bearer")


@pytest.fixture(scope="module")
def service_account_token2(create_service_account, audience):
    """Create a non-authorized service account and request its bound token with the hostname as audience"""
    service_account = create_service_account("no-auth")
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth2(service_account_token2):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(service_account_token2, "Bearer")
