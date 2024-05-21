"""Tests for basic authenticated rate limiting"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.policy.authorization import ValueFrom, JsonResponse
from testsuite.policy.rate_limit_policy import Limit


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit(
        "basic", [Limit(5, 60)], counters=[r"metadata.filter_metadata.envoy\.filters\.http\.ext_authz.identity.user"]
    )
    return rate_limit


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Adds keycloak identity and JSON injection, that wraps the response as Envoy Dynamic Metadata for rate limit"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    authorization.responses.add_success_dynamic(
        "identity", JsonResponse({"user": ValueFrom("auth.identity.preferred_username")})
    )
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def auth2(keycloak, blame):
    """Creates new Keycloak user and returns its authentication object for HTTPX"""
    name = keycloak.user.username + "-test2"
    user = keycloak.realm.create_user(name, "password", email=f"{blame('test')}@test.com")
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.mark.parametrize("rate_limit", ["route", "gateway"], indirect=True)
def test_authz_limit(client, auth, auth2):
    """Tests that rate limit is applied for two users independently"""
    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
    assert client.get("/get", auth=auth2).status_code == 200
