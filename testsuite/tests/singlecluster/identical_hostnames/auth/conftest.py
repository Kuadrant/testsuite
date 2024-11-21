"""Conftest for "identical hostname" tests"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """1st 'allow-all' Authorization object"""
    authorization.authorization.add_opa_policy("rego", "allow = true")
    return authorization


@pytest.fixture(scope="module")
def rate_limit():
    """
    For these tests RateLimitPolicy is not required
    """
    return None
