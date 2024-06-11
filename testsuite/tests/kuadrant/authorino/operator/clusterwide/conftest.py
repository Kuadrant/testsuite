"""Conftest for clusterwide tests"""

import pytest

from testsuite.gateway.envoy.route import EnvoyVirtualRoute
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
def route2(request, gateway, blame, hostname2):
    """Create virtual route for the second hostname"""
    route = EnvoyVirtualRoute.create_instance(gateway.openshift, blame("route"), gateway)
    route.add_hostname(hostname2.hostname)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def authorization2(route2, blame, openshift2, label, oidc_provider):
    """Second valid hostname"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), route2, labels={"testRun": label})
    auth.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return auth


@pytest.fixture(scope="module")
def client2(hostname2):
    """Client for second AuthConfig"""
    client = hostname2.client()
    yield client
    client.close()


@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, authorization2):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization2.delete)
    authorization2.commit()
    authorization2.wait_for_ready()
