"""Tests basic authentication with RHSSO/Auth0 as identity provider"""
import pytest


@pytest.mark.parametrize(("client_fixture", "auth_fixture"), [
    pytest.param("rhsso_client", "auth", id="RHSSO"),
    pytest.param("auth0_client", "auth0_auth", id="Auth0"),
])
def test_correct_auth(client_fixture, auth_fixture, request):
    """Tests correct auth"""
    client = request.getfixturevalue(client_fixture)
    auth = request.getfixturevalue(auth_fixture)
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


@pytest.mark.parametrize("client_fixture", [
    pytest.param("rhsso_client", id="RHSSO"),
    pytest.param("auth0_client", id="Auth0"),
])
def test_no_auth(client_fixture, request):
    """Tests request without any auth"""
    client = request.getfixturevalue(client_fixture)
    response = client.get("/get")
    assert response.status_code == 401


@pytest.mark.parametrize("client_fixture", [
    pytest.param("rhsso_client", id="RHSSO"),
    pytest.param("auth0_client", id="Auth0"),
])
def test_wrong_auth(client_fixture, request):
    """Tests request with wrong token"""
    client = request.getfixturevalue(client_fixture)
    response = client.get("/get", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401
