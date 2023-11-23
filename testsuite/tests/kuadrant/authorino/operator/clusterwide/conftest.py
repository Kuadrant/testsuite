"""Conftest for clusterwide tests"""
import pytest

from testsuite.policy.authorization.auth_config import AuthConfig


@pytest.fixture(scope="module")
def authorino_parameters():
    """Deploy Authorino in ClusterWide mode"""
    return {"cluster_wide": True}


@pytest.fixture(scope="module")
def hostname2(exposer, gateway, blame):
    """Second route for the envoy"""
    return exposer.expose_hostname(blame("hostname"), gateway)


@pytest.fixture(scope="module")
def authorization2(route, hostname2, blame, openshift2, module_label, oidc_provider):
    """Second valid hostname"""
    route.add_hostname(hostname2.hostname)
    auth = AuthConfig.create_instance(openshift2, blame("ac"), route, labels={"testRun": module_label})
    auth.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
    return auth


@pytest.fixture(scope="module")
def client2(hostname2):
    """Client for second AuthConfig"""
    client = hostname2.client()
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, authorization2):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization2.delete)
    authorization2.commit()
