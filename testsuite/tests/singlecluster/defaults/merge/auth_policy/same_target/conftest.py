"""Conftest for merge strategy tests for same target for auth policies"""
import functools

import pytest

@pytest.fixture(scope="module")
def authorization(authorization, user_api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    authorization.defaults.identity.add_api_key("api-key", selector=user_api_key.selector)
    return authorization


# Define your custom decorator
def auth_parametrize_gateway_route(func):
    """
    A custom decorator to apply specific authorization parameterization.
    Equivalent to:
    @pytest.mark.parametrize(
        "authorization, global_authorization",
        [("gateway", "gateway"), ("route", "route")],
        indirect=True,
        ids=["gateway", "route"]
    )
    """
    @pytest.mark.parametrize(
        "authorization, global_authorization",
        [("gateway", "gateway"), ("route", "route")],
        indirect=True,
        ids=["gateway", "route"]
    )
    @functools.wraps(func) # Use functools.wraps to preserve function metadata
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# --- How to use it ---