"""Tests AuthConfig with multiple specified hosts"""

import pytest

pytestmark = [pytest.mark.authorino]


def test_original_host(client, auth):
    """Tests correct host"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_second_host(client2, auth):
    """Tests correct host"""
    response = client2.get("/get", auth=auth)
    assert response.status_code == 200
