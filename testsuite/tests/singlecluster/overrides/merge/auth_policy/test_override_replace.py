"""Test override overriding another policy aimed at the same Gateway Listener."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Strategy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, route, user_api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_api_key("basic", selector=user_api_key.selector)
    return auth_policy


@pytest.fixture(scope="module")
def override_auth_policy(cluster, blame, keycloak, module_label, route, oidc_provider):
    """
    Create an AuthPolicy with authentication for an admin with same target as one default.
    Also adds authorization for only admins.
    """
    auth_policy = AuthPolicy.create_instance(cluster, blame("omp"), route, labels={"testRun": module_label})
    auth_policy.overrides.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    auth_policy.overrides.metadata.add_user_info("user-info", "basic")
    auth_policy.overrides.authorization.add_auth_rules(
        "rule", [Pattern("auth.metadata.user-info.email", "eq", keycloak.user.properties["email"])]
    )
    auth_policy.overrides.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="function", autouse=True)
def commit(request, route, authorization, override_auth_policy):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [override_auth_policy, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_override_replace(client, authorization, override_auth_policy, auth, admin_auth):
    """Test AuthPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert authorization.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "AuthPolicy is overridden by " f"[{override_auth_policy.namespace()}/{override_auth_policy.name()}]",
        )
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=auth).status_code == 200  # user authentication overrides.
    assert client.get("/get", auth=admin_auth).status_code == 401  # admin authentication is being overridden.
