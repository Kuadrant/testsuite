"""Tests for authenticated rate limit, but only for anonymous users"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization import Pattern, JsonResponse, ValueFrom
from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy only for anonymous users"""
    rate_limit.add_limit(
        "basic",
        [Limit(5, 10)],
        when=[
            Pattern(
                selector=r"metadata.filter_metadata.envoy\.filters\.http\.ext_authz.identity.anonymous",
                operator="eq",
                value="true",
            )
        ],
    )
    return rate_limit


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add oidc and anonymous identity with low priority to the AuthConfig"""
    authorization.identity.add_anonymous("anonymous", priority=1)
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])

    # curly brackets are added to response as it stringifies the anonymous output.
    authorization.responses.add_success_dynamic(
        "identity", JsonResponse({"anonymous": ValueFrom("{auth.identity.anonymous}")})
    )
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


def test_no_limit_for_auth_user(client, auth):
    """Test that no limit is not applied for authenticated user"""
    responses = client.get_many("/get", 7, auth=auth)
    responses.assert_all(status_code=200)


def test_anonymous_identity(client, auth):
    """Test that an anonymous requests are correctly limited"""
    assert client.get("/get", auth=auth).status_code == 200

    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert client.get("/get").status_code == 429
    assert client.get("/get", auth=auth).status_code == 200
