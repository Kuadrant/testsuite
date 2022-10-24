"""Test for API key identity context"""
import json

import pytest


@pytest.fixture(scope="module")
def authorization(authorization, module_label):
    """Setup AuthConfig for test"""
    authorization.identity.api_key("api_key", match_label=module_label)
    authorization.responses.add({"name": "auth-json", "json": {
        "properties": [{"name": "auth", "valueFrom": {"authJSON": "auth.identity"}}]}})
    return authorization


def tests_api_key_context(client, auth, api_key, module_label, testconfig):
    """
    Test:
        - Make request with API key authentication
        - Assert that response has the right information in context
    """
    response = client.get("get", auth=auth)
    assert response.status_code == 200
    identity = json.loads(response.json()["headers"]["Auth-Json"])["auth"]
    assert identity['data']['api_key'] == api_key.model.data.api_key
    assert identity["metadata"]["namespace"] == testconfig["openshift"].project
    assert identity["metadata"]["labels"]["group"] == module_label
