"""Test host removal"""


def test_removing_host(client, client2, auth, authorization, second_route):
    """Tests that after removal of the second host, it stops working, while the first one still works"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client2.get("/get", auth=auth)
    assert response.status_code == 200

    authorization.remove_host(second_route.hostname)

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client2.get("/get", auth=auth)
    assert response.status_code == 404
