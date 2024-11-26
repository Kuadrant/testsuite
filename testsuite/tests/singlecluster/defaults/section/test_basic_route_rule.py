"""Test enforcement of policies with defaults targeting a specific HTTPRouteRule"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(10, "10s")


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, route, oidc_provider):
    """Add oidc identity targeting the first HTTPRouteRule"""
    authorization = AuthPolicy.create_instance(
        cluster, blame("authz"), route, labels={"testRun": module_label}, section_name="rule-1"
    )
    authorization.defaults.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label}
    )
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


def test_basic_authorization(client, auth):
    """Test the defaults policies are correctly applied to the HTTPRouteRule."""
    assert client.get("/get").status_code == 401

    responses = client.get_many("/get", LIMIT.limit - 1, auth=auth)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get", auth=auth).status_code == 429
