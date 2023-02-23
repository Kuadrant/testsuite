"""Test that Authorino can reconcile resources in multiple namespaces"""
import pytest


@pytest.mark.parametrize(
    "client_fixture",
    [
        pytest.param("client", id="First namespace"),
        pytest.param("client2", id="Second namespace"),
    ],
)
def test_auth(request, client_fixture, auth):
    """Tests that both AuthConfigs were reconciled in both namespaces"""
    client = request.getfixturevalue(client_fixture)
    response = client.get("/get")
    assert response.status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200
