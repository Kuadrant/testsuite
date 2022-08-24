"""Conftest for clusterwide tests"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


@pytest.fixture(scope="module")
def cluster_wide():
    """Deploy Authorino in ClusterWide mode"""
    return True


@pytest.fixture(scope="module")
def hostname2(envoy, blame):
    """Second route for the envoy"""
    return envoy.create_route(blame("route")).model.spec.host


@pytest.fixture(scope="module")
def authorization2(hostname2, blame, openshift2, module_label, rhsso_service_info):
    """Second valid hostname"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), hostname2, labels={"testRun": module_label})
    auth.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return auth


@pytest.fixture(scope="module")
def client2(hostname2, envoy):
    """Client for second AuthConfig"""
    client = envoy.client()
    client.base_url = f"http://{hostname2}"
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def commit(commit, authorization2):
    """Commits all important stuff before tests"""
    authorization2.commit()
    yield
    authorization2.delete()
