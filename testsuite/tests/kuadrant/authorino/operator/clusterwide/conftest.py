"""Conftest for clusterwide tests"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


@pytest.fixture(scope="module")
def authorino_parameters():
    """Deploy Authorino in ClusterWide mode"""
    return {"cluster_wide": True}


@pytest.fixture(scope="module")
def route2(proxy, blame):
    """Second route for the envoy"""
    return proxy.expose_hostname(blame("route"))


@pytest.fixture(scope="module")
def authorization2(route2, blame, openshift2, module_label, oidc_provider):
    """Second valid hostname"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), route2, labels={"testRun": module_label})
    auth.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
    return auth


@pytest.fixture(scope="module")
def client2(route2):
    """Client for second AuthConfig"""
    client = route2.client()
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, authorization2):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization2.delete)
    authorization2.commit()
