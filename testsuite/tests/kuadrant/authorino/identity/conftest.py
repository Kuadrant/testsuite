"""Conftest for all Identity tests"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """For Identity tests remove all identities previously setup"""
    authorization.identity.clear_all()
    return authorization
