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
def authorization2(hostname2, blame, openshift2, label, rhsso_service_info):
    """Second valid hostname"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), hostname2, labels={"testRun": label})
    auth.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return auth


@pytest.fixture(scope="module")
def client2(hostname2, authorization2, envoy):
    """Client for second AuthConfig"""
    client = envoy.client()
    client.base_url = f"http://{hostname2}"
    authorization2.commit()
    yield client
    client.close()
    authorization2.delete()
