"""Conftest for reconciliation tests"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add anonymous identity. This is needed as we can't create authorization without any rule"""
    authorization.identity.add_anonymous("anonymous")
    return authorization


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Only commit authorization"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()
