"""Conftest for SubjectAccessReview related tests."""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kubernetes.cluster_role import ClusterRole, ClusterRoleBinding


@pytest.fixture(scope="module")
def cluster_role(request, cluster, blame, module_label):
    """Creates and returns a ClusterRole"""
    rules = [{"nonResourceURLs": ["/get"], "verbs": ["get"]}]
    cluster_role = ClusterRole.create_instance(cluster, blame("cr"), rules, labels={"app": module_label})
    request.addfinalizer(cluster_role.delete)
    cluster_role.commit()
    return cluster_role


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
def bound_service_account_token(cluster_role, create_service_account, create_cluster_role_binding, audience):
    """Create a ServiceAccount, bind it to a ClusterRole and return its token with a given audience"""
    service_account = create_service_account("tkn-auth")
    create_cluster_role_binding(cluster_role.model.metadata.name, [service_account.model.metadata.name])
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth(bound_service_account_token):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(bound_service_account_token, "Bearer")
