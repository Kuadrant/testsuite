"""Conftest for merge strategy tests for same target for auth policies"""

import pytest

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route)"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def authorization(cluster, blame, user_label, target, user_api_key):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), target, labels={"testRun": user_label})
    auth_policy.identity.add_api_key("api-key", selector=user_api_key.selector)
    return auth_policy
