"""Conftest for merge strategy tests for same target for auth policies"""

import pytest

from testsuite.kuadrant.policy import Strategy
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def authorization(cluster, blame, user_label, route, user_api_key):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": user_label})
    auth_policy.identity.add_api_key("basic", selector=user_api_key.selector)
    return auth_policy


@pytest.fixture(scope="module")
def override_merge_authorization(cluster, blame, admin_label, route, admin_api_key):
    """
    Create an AuthPolicy with authentication for an admin with same target as one default.
    Also adds authorization for only admins.
    """
    auth_policy = AuthPolicy.create_instance(cluster, blame("omp"), route, labels={"testRun": admin_label})
    auth_policy.overrides.identity.add_api_key("basic", selector=admin_api_key.selector)
    auth_policy.overrides.authorization.add_opa_policy(
        "only-admins",
        """
        groups := split(object.get(input.auth.identity.metadata.annotations, "kuadrant.io/groups", ""), ",")
                allow { groups[_] == "admins" }""",
    )
    auth_policy.overrides.strategy(Strategy.MERGE)
    return auth_policy
