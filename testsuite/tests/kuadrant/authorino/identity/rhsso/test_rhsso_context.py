"""Test for RHSSO identity context"""
import json
import time

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """Setup AuthConfig for test"""
    authorization.responses.add({
        "name": "auth-json",
        "json": {
            "properties": [{
                "name": "auth",
                "valueFrom": {
                    "authJSON": "auth.identity"
                }
            }, {
                "name": "context",
                "valueFrom": {
                    "authJSON": "context.request.http.headers.authorization"
                }
            }]
        }
    })
    return authorization


@pytest.fixture(scope="module")
def realm_role(rhsso, realm_role):
    """Add realm role to rhsso user"""
    rhsso.user.assign_realm_role(realm_role)
    return realm_role


def tests_rhsso_context(client, auth, rhsso, realm_role):
    """
    Test:
        - Make request with RHSSO authentication
        - Assert that response has the right information in context
    """
    response = client.get("get", auth=auth)
    assert response.status_code == 200
    auth_json = json.loads(response.json()["headers"]["Auth-Json"])
    identity = auth_json["auth"]
    now = time.time()
    assert rhsso.well_known["issuer"] == identity["iss"]
    assert identity["azp"] == rhsso.client_name
    assert float(identity["exp"]) > now
    assert float(identity["iat"]) <= now
    assert auth_json["context"] == f"Bearer {auth.token.access_token}"
    assert realm_role["name"] in identity["realm_access"]["roles"]
    assert identity['email'] == rhsso.user.properties["email"]
