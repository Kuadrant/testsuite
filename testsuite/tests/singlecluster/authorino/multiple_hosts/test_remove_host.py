"""Test host removal"""

import pytest

pytestmark = [pytest.mark.authorino]


def test_removing_host(client, client2, auth, route, second_hostname):
    """Tests that after removal of the second host, it stops working, while the first one still works"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client2.get("/get", auth=auth)
    assert response.status_code == 200

    route.remove_hostname(second_hostname.hostname)

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    with second_hostname.client(retry_codes={200}) as failing_client:
        response = failing_client.get("/get", auth=auth)
        assert response.status_code == 404
