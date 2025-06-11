"""Conftest for overrides merge strategy tests for AuthPolicies on same target"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization, user_api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    authorization.defaults.identity.add_api_key("api-key", selector=user_api_key.selector)
    return authorization
