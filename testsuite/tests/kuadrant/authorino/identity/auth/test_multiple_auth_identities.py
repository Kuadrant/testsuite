"""
Tests for multiple auth identities (RHSSO + Auth0)
"""

import pytest


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def client(auth0_authorization, rhsso_authorization, envoy):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = envoy.client()
    yield client
    client.close()


def test_correct_auth(client, auth, auth0_auth):
    """Tests correct auth"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get", auth=auth0_auth)
    assert response.status_code == 200


def test_no_auth(client, request):
    """Tests request without any auth"""
    response = client.get("/get")
    assert response.status_code == 401


def test_wrong_auth(client, request):
    """Tests request with wrong token"""
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
