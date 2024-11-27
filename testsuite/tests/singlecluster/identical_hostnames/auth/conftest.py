"""Conftest for "identical hostname" tests"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """1st 'allow-all' Authorization object"""
    authorization.authorization.add_opa_policy("rego", "allow = true")
    return authorization
