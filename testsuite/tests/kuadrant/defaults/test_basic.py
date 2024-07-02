"""Test basic enforcement of the rules inside the 'defaults' block of the AuthPolicy and RateLimitPolicy"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.policy.rate_limit_policy import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

LIMIT = Limit(3, 5)


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add oidc identity to defaults block of AuthPolicy"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"], defaults=True)
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic requests limit to defaults block of RateLimitPolicy"""
    rate_limit.add_limit("basic", [LIMIT], defaults=True)
    return rate_limit


def test_basic(route, authorization, rate_limit, client, auth):
    """Test if rules inside defaults block are enforced like any other normal rule"""
    route.refresh()
    assert route.is_affected_by(authorization)

    response = client.get("/get")
    assert response.status_code == 401  # assert that AuthPolicy is enforced

    assert route.is_affected_by(rate_limit)

    responses = client.get_many("/get", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429  # assert that RateLimitPolicy is enforced
