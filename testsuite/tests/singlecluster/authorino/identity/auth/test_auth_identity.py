"""Tests basic authentication with Keycloak/Auth0 as identity provider"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc import OIDCProvider
from testsuite.oidc.keycloak import Keycloak

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add Keycloak identity to AuthConfig"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


def oidc_provider(request) -> OIDCProvider:
    """Fixture which enables switching out OIDC providers for individual modules"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def wrong_auth(oidc_provider, auth0, keycloak):
    """Different (but valid) auth than was configured"""
    token = keycloak.get_token
    if isinstance(oidc_provider, Keycloak):
        token = auth0.get_token
    return HttpxOidcClientAuth(token)


@pytest.mark.parametrize(
    "oidc_provider",
    [pytest.param("keycloak"), pytest.param("auth0")],
    indirect=True,
)
def test_auth_identity(client, auth, wrong_auth):
    """Tests endpoint protection with auth identity"""
    response = client.get("/get")
    assert response.status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get", auth=wrong_auth)
    assert response.status_code == 401

    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
