"""Tests that wrapperKey property returns value in the correct header"""
import json

import pytest


@pytest.fixture(scope="module", params=["123456789", "standardCharacters", "specialcharacters/+*-."])
def header_name(request):
    """Name of the headers"""
    return request.param


@pytest.fixture(scope="module")
def responses(header_name):
    """Returns response to be added to the AuthConfig"""
    return [{
        "name": "header",
        "wrapperKey": header_name,
        "json": {
            "properties": [{
                "name": "anything",
                "value": "one"
            }]
        }
    }]


def test_wrapper_key_with(auth, client, header_name):
    """Tests that value in correct Header"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    data = response.json()["headers"].get(header_name.capitalize(), None)
    assert data is not None, f"Headers from response ({header_name.capitalize()}) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"
