"""Conftest for all Identity tests"""
import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """For Identity tests remove all identities previously setup"""
    authorization.identity.remove_all()
    return authorization
