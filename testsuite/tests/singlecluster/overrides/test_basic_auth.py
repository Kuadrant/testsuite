"""Test basic enforcement of the rules inside the 'overrides' block of the RateLimitPolicy assigned to a Gateway"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization(route, gateway, blame, cluster, label, oidc_provider):  # pylint: disable=unused-argument
    """Add oidc identity to overrides block of gateway-attached AuthPolicy"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway, labels={"testRun": label})
    auth_policy.overrides.identity.add_oidc("override", oidc_provider.well_known["issuer"])
    return auth_policy


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit():
    """No RateLimitPolicy is required for this test"""
    return None


def test_basic_auth(route, authorization, client, auth):
    """Test if rules inside overrides block of Gateway's AuthPolicy are inherited by the HTTPRoute
    and enforced like any other normal rule"""
    route.refresh()
    assert route.is_affected_by(authorization)

    response = client.get("/get")
    assert response.status_code == 401
    assert client.get("/get", auth=auth).status_code == 200  # assert that AuthPolicy is enforced
