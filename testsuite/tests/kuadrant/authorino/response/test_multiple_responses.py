"""Tests multiple responses specified"""
import json

import pytest


@pytest.fixture(scope="module")
def responses():
    """Returns response to be added to the AuthConfig"""
    return [{"name": "Header",
            "json": {
                "properties": [
                    {"name": "anything", "value": "one"}
                ]
            }},
            {"name": "X-Test",
             "json": {
                 "properties": [
                     {"name": "anything", "value": "two"}
                 ]
             }},
            ]


def test_multiple_responses(auth, client):
    """Test that both headers are present"""
    response = client.get("/get", auth=auth)

    assert response.status_code == 200
    data = response.json()["headers"].get("Header", None)
    assert data is not None, "Headers from first response (Header) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"

    data = response.json()["headers"].get("X-Test", None)
    assert data is not None, "Headers from second response (X-Test) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "two"
