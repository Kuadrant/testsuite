"""Tests for PlanPolicy functionality including authentication and rate limiting."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.extensions.plan_policy import PlanPolicy, Plan


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.extensions]

PLANS = {
    "gold": Plan(
        tier="gold",
        predicate='has(auth.identity) && auth.identity.planID == "gold"',
        limits={"custom": [{"limit": 3, "window": "20s"}]},
    ),
    "silver": Plan(
        tier="silver",
        predicate='has(auth.identity) && auth.identity.planID == "silver"',
        limits={"custom": [{"limit": 2, "window": "20s"}]},
    ),
    "bronze": Plan(
        tier="bronze",
        predicate='has(auth.identity) && auth.identity.planID == "bronze"',
        limits={"custom": [{"limit": 1, "window": "20s"}]},
    ),
}


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route)"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def realm_with_attributes(keycloak):
    """
    Ensure the realm allows a custom user attribute and configure client mapper.
    """
    keycloak.realm.add_user_attributes("planID", "Plan ID")
    keycloak.client.add_user_attribute_mapper("planID", "planID")


@pytest.fixture(scope="module")
def user_with_gold_plan(keycloak, realm_with_attributes, blame):  # pylint: disable=unused-argument
    """
    Creates new user with "gold" plan.
    """
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"planID": ["gold"]})
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_silver_plan(keycloak, realm_with_attributes, blame):  # pylint: disable=unused-argument
    """
    Creates new user with "silver" plan.
    """
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"planID": ["silver"]})
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_bronze_plan(keycloak, realm_with_attributes, blame):  # pylint: disable=unused-argument
    """
    Creates new user with "bronze" plan.
    """
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"planID": ["bronze"]})
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
    plan_policy.add_plans(PLANS)
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
    "tier, allowed_requests", [(tier, plan.limits["custom"][0]["limit"]) for tier, plan in PLANS.items()]
)
def test_plan_policy(client, tier, allowed_requests, request):
    """
    Test PlanPolicy enforcement across different tiers and rate limits.

    Verifies that:
    - Users with valid tokens can make requests up to their tier limit
    - Requests beyond the limit are rate-limited (429)
    - Invalid tokens are rejected with 401
    """
    user_auth = request.getfixturevalue(f"user_with_{tier}_plan")

    responses = client.get_many("/get", count=allowed_requests, auth=user_auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=user_auth).status_code == 429

    response = client.get("/get", headers={"Authorization": "Bearer invalid-token123"})
    assert response is not None
    assert response.status_code == 401
