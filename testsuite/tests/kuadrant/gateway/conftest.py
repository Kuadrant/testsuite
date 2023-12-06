"""Conftest for gateway tests"""
import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def kuadrant(kuadrant):
    """Skip if not running on Kuadrant"""
    if not kuadrant:
        pytest.skip("Gateway tests are only for Kuadrant")
    return kuadrant


@pytest.fixture(scope="module")
def gateway_ready(gateway):
    """Returns ready gateway"""
    gateway.wait_for_ready()
    return gateway


@pytest.fixture(scope="module")
def authorization(gateway_ready, route, oidc_provider, authorization_name, openshift, module_label):
    # pylint: disable=unused-argument
    """Create AuthPolicy attached to gateway"""
    authorization = AuthPolicy.create_instance(
        openshift, authorization_name, gateway_ready, labels={"testRun": module_label}
    )
    authorization.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")
