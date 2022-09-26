"""Test for anonymous identity context"""
import json

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """Setup AuthConfig for test"""
    authorization.add_anonymous_identity("anonymous")
    authorization.add_response({"name": "auth-json", "json": {
        "properties": [{"name": "auth", "valueFrom": {"authJSON": "auth.identity.anonymous"}}]}})
    return authorization


def test_anonymous_context(client):
    """
    Test:
        - Make request without authentication
        - Assert that response has the right information in context
    """
    response = client.get("/get")
    assert json.loads(response.json()["headers"]["Auth-Json"])["auth"]
    assert response.status_code == 200
