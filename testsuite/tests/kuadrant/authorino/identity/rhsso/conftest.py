"""Conftest for authorino rhsso tests"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="session")
def oidc_provider(rhsso):
    """Fixture which enables switching out OIDC providers for individual modules"""
    return rhsso


@pytest.fixture(scope="module")
def authorization(authorization, rhsso, jwt_ttl):
    """Add RHSSO identity to AuthConfig"""
    authorization.identity.add_oidc(
        "rhsso",
        rhsso.well_known["issuer"],
        ttl=jwt_ttl,
    )
    return authorization


@pytest.fixture(scope="module")
def realm_role(rhsso, blame):
    """Creates new realm role"""
    return rhsso.realm.create_realm_role(blame("role"))


@pytest.fixture(scope="module")
def jwt_ttl():
    """
    Returns TTL in seconds for Authorino to trigger OIDC discovery and update its cache.
    Some tests might sleep for this long to make sure TTL is reached so keep this number reasonably low.
    """
    return 30


@pytest.fixture(scope="module")
def create_jwt_auth(rhsso, auth):
    """Creates a new Auth using a new JWT (JSON Web Token)"""

    def _create_jwt_auth():
        new_token = rhsso.get_token(auth.username, auth.password)
        return HttpxOidcClientAuth(new_token)

    return _create_jwt_auth
