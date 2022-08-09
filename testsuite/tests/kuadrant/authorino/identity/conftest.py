"""Conftest for all Identity tests"""
import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """For Identity tests remove all identities previously setup"""
    authorization.remove_all_identities()
    return authorization
