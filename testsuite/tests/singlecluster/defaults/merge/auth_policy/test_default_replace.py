"""Test gateway level default merging with and being partially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Strategy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(cluster, blame, admin_label, route, oidc_provider):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": admin_label})
    auth_policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    return auth_policy


@pytest.fixture(scope="module")
def global_authorization(cluster, blame, keycloak, user_label, route, admin_api_key):
    """
    Create an AuthPolicy with authentication for an admin with same target as one default.
    Also adds authorization for only admins.
    """
    auth_policy = AuthPolicy.create_instance(cluster, blame("dmp"), route, labels={"testRun": user_label})
    auth_policy.defaults.identity.add_api_key("basic", selector=admin_api_key.selector)
    auth_policy.defaults.metadata.add_user_info("user-info", "basic")
    auth_policy.defaults.authorization.add_auth_rules(
        "rule", [Pattern("auth.metadata.user-info.email", "eq", keycloak.user.properties["email"])]
    )
    auth_policy.defaults.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_default_replace(client, global_authorization, auth, admin_auth):
    """Test Gateway default policy being partially overriden when another policy with the same target is created."""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=auth).status_code == 200  # user authentication works as expected.
    assert client.get("/get", auth=admin_auth).status_code == 401  # admin authentication is being overridden.
