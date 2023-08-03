"""Tests that simplest JSON response returns correct header"""
import json

import pytest
from testsuite.objects import ResponseProperties, Value


@pytest.fixture(scope="module")
def responses():
    """Returns response to be added to the AuthConfig"""
    return [ResponseProperties(name="header", json=[Value("one", name="anything")])]


def test_simple_response_with(auth, client):
    """Tests simple response"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    data = response.json()["headers"].get("Header", None)
    assert data is not None, "Header from response (Header) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"
