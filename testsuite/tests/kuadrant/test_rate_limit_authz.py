"""Tests for basic authenticated rate limiting"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.objects import ValueFrom
from testsuite.openshift.objects.rate_limit import Limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit(
        "basic", [Limit(5, 60)], counters=[r"metadata.filter_metadata.envoy\.filters\.http\.ext_authz.identity.user"]
    )
    return rate_limit


@pytest.fixture(scope="module")
def authorization(authorization):
    """Adds JSON injection, that wraps the response as Envoy Dynamic Metadata for rate limit"""
    authorization.responses.add_json(
        "identity", {"user": ValueFrom("auth.identity.preferred_username")}, wrapper="dynamicMetadata"
    )
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def auth2(rhsso, blame):
    """Creates new RHSSO user and returns its authentication object for HTTPX"""
    name = rhsso.user.username + "-test2"
    user = rhsso.realm.create_user(name, "password", email=f"{blame('test')}@test.com")
    return HttpxOidcClientAuth.from_user(rhsso.get_token, user=user)


def test_authz_limit(client, auth, auth2):
    """Tests that rate limit is applied for two users independently"""
    responses = client.get_many("/get", 5, auth=auth)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get", auth=auth).status_code == 429
    assert client.get("/get", auth=auth2).status_code == 200
