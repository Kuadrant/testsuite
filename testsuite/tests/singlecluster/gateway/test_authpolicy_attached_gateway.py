"""Test for AuthPolicy attached directly to gateway"""

import pytest

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def rate_limit():
    """Basic gateway test doesn't utilize RateLimitPolicy component"""
    return None


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/pull/287")
def test_authpolicy_attached_gateway(client, auth):
    """Test if AuthPolicy attached directly to gateway works"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get")
    assert response.status_code == 401
