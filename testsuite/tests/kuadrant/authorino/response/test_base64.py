"""
Tests base64 decoding abilities of Authorino and it's escaping of strings
"""
import json
from base64 import standard_b64encode

import pytest


@pytest.fixture(scope="module")
def responses():
    """Returns response to be added to the AuthConfig"""
    return [
        {
            "name": "header",
            "json": {
                "properties": [
                    {
                        "name": "anything",
                        "valueFrom": {"authJSON": "context.request.http.headers.test|@base64:decode"},
                    }
                ]
            },
        }
    ]


@pytest.mark.parametrize(
    "string", ['My name is "John"', 'My name is "John', "My name is 'John'", "My name is 'John", '{"json": true}']
)
def test_base64(auth, client, string):
    """Tests that base64 decoding filter works"""
    encoded = standard_b64encode(string.encode()).decode()
    response = client.get("/get", auth=auth, headers={"test": encoded})
    assert response.status_code == 200

    data = response.json()["headers"].get("Header")
    assert data

    assert json.loads(data)["anything"] == string
