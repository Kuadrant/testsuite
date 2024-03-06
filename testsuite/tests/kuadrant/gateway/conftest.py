"""Conftest for gateway tests"""

import pytest

from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="module")
def gateway(request, openshift, blame, wildcard_domain, module_label):
    """Returns ready gateway"""
    gw = KuadrantGateway.create_instance(openshift, blame("gw"), wildcard_domain, {"app": module_label})
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready(timeout=10 * 60)
    return gw


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    # pylint: disable=unused-argument
    """Create AuthPolicy attached to gateway"""
    authorization.identity.add_oidc("rhsso", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")
