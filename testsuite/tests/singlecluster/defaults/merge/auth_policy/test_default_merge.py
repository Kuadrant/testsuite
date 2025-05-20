"""Test gateway level default merging with and not being overridden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization import Credentials
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Strategy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(cluster, blame, user_api_key, module_label, route):
    """Create an AuthPolicy with authentication for a simple user with same target as one default"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_api_key("second-api-key", selector=user_api_key.selector)
    return auth_policy


def test_default_merge(client, authorization, global_authorization, user_auth, admin_auth):
    """Both policies are enforced and not being overridden"""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )
    assert authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=user_auth).status_code == 403  # user authentication works, but it is not authorized.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin authentication with api key.
