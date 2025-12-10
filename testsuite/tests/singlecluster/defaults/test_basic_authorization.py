"""Test basic enforcement of the rules inside the 'defaults' block of the AuthPolicy"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth

pytestmark = [pytest.mark.defaults_overrides, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add oidc identity to defaults block of AuthPolicy"""
    authorization.defaults.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit():
    """No RateLimitPolicy is required for this test"""
    return None


@pytest.mark.parametrize("authorization", ["route", "gateway"], indirect=True)
def test_basic_authorization(authorization, route, client, auth):
    """Test that default identity is applied successfully and shows affected status in the route"""
    route.refresh()
    assert route.is_affected_by(authorization)

    assert client.get("/get").status_code == 401
    assert client.get("/get", auth=auth).status_code == 200  # assert that AuthPolicy is enforced
