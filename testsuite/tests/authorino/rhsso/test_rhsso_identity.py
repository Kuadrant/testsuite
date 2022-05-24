"""Tests basic authentication with RHSSO as identity provider"""


def test_correct_auth(client, auth):
    """Tests correct auth"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_no_auth(client):
    """Tests request without any auth"""
    response = client.get("/get")
    assert response.status_code == 401


def test_wrong_auth(client):
    """Tests request with wrong token"""
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 403
