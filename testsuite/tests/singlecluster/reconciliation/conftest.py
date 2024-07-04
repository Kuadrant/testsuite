"""Conftest for reconciliation tests"""

import pytest


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Only commit authorization"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()
