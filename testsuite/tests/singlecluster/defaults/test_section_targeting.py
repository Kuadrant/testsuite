"""Test enforcement of policies with defaults targeting a specifics gateway/route section"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

LIMIT = Limit(5, "10s")


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route) and the target section name"""
    return request.getfixturevalue(request.param[0]), request.param[1]


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def authorization(cluster, target, route, oidc_provider, module_label, blame):  # pylint: disable=unused-argument
    """Add oidc identity to defaults block of AuthPolicy"""
    authorization = AuthPolicy.create_instance(
        cluster, blame("authz"), target[0], labels={"testRun": module_label}, section_name=target[1]
    )
    authorization.defaults.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(cluster, target, route, module_label, blame):  # pylint: disable=unused-argument
    """Add a RateLimitPolicy targeting specific section"""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), target[0], target[1], labels={"testRun": module_label}
    )
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.mark.parametrize(
    "target",
    [pytest.param(("gateway", "api"), id="gateway"), pytest.param(("route", "rule-1"), id="route")],
    indirect=True,
)
def test_basic_listener(client, auth):
    """Test the defaults policies are correctly applied to the target section"""
    assert client.get("/get").status_code == 401

    responses = client.get_many("/get", LIMIT.limit - 1, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429
