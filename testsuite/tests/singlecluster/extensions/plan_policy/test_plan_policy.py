"""Tests for PlanPolicy functionality including authentication and rate limiting."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.plan_policy import PlanPolicy, Plan


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]

PLANS = {
    "gold": Plan(
        tier="gold",
        predicate='has(auth.identity) && auth.identity.planID == "gold"',
        limits={"custom": [{"limit": 5, "window": "10s"}]},
    ),
    "silver": Plan(
        tier="silver",
        predicate='has(auth.identity) && auth.identity.planID == "silver"',
        limits={"custom": [{"limit": 3, "window": "20s"}]},
    ),
    "bronze": Plan(
        tier="bronze",
        predicate='has(auth.identity) && auth.identity.planID == "bronze"',
        limits={"daily": 2},
    ),
}


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route)"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def keycloak(keycloak):
    """
    Ensure the realm allows a custom user attribute and configure client mapper.
    """
    keycloak.realm.add_user_attributes("planID", "Plan ID")
    keycloak.client.add_user_attribute_mapper("planID", "planID")
    return keycloak


@pytest.fixture(scope="module")
def user_with_plan(request, keycloak, blame):
    """
    Creates new user with specified plan tier.
    """
    plan_tier = request.param
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"planID": [plan_tier]})
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add Keycloak identity to AuthConfig"""
    authorization.identity.add_oidc("keycloak", keycloak.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def plan_policy(cluster, blame, target):
    """Create PlanPolicy targeting the route/gateway"""
    plan_policy = PlanPolicy.create_instance(cluster, blame("my-plan"), target)
    for plan in PLANS.values():
        plan_policy.add_plan(plan)
    return plan_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, plan_policy, authorization):
    """Commits all important stuff before tests"""
    for component in [authorization, plan_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()


@pytest.mark.parametrize("target", ["route", "gateway"], indirect=True)
@pytest.mark.parametrize(
    "user_with_plan, allowed_requests",
    [
        (tier, plan.limits["custom"][0]["limit"] if "custom" in plan.limits else list(plan.limits.values())[0])
        for tier, plan in PLANS.items()
    ],
    indirect=["user_with_plan"],
)
def test_plan_policy(client, user_with_plan, allowed_requests):
    """
    Test PlanPolicy enforcement across different tiers and rate limits.

    Verifies that:
    - Users with valid tokens can make requests up to their tier limit
    - Requests beyond the limit are rate-limited (429)
    """
    user_auth = user_with_plan

    responses = client.get_many("/get", count=allowed_requests, auth=user_auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=user_auth).status_code == 429


@pytest.mark.parametrize("target", ["route", "gateway"], indirect=True)
def test_plan_policy_unauthorized(client):
    """
    Test that invalid tokens are rejected with 401.
    """
    response = client.get("/get", headers={"Authorization": "Bearer invalid-token123"})
    assert response is not None
    assert response.status_code == 401
