"""Test for Keycloak identity context"""

import json
import time

import pytest

from testsuite.kuadrant.policy.authorization import ValueFrom, JsonResponse

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Setup AuthConfig for test"""
    authorization.responses.add_success_header(
        "auth-json",
        JsonResponse(
            {
                "auth": ValueFrom("auth.identity"),
                "context": ValueFrom("context.request.http.headers.authorization"),
            }
        ),
    )
    return authorization


@pytest.fixture(scope="module")
def realm_role(keycloak, realm_role):
    """Add realm role to Keycloak user"""
    keycloak.user.assign_realm_role(realm_role)
    return realm_role


def test_keycloak_context(client, auth, keycloak, realm_role):
    """
    Test:
        - Make request with Keycloak authentication
        - Assert that response has the right information in context
    """
    response = client.get("get", auth=auth)
    assert response.status_code == 200
    auth_json = json.loads(response.json()["headers"]["Auth-Json"])
    identity = auth_json["auth"]
    now = time.time()
    assert keycloak.well_known["issuer"] == identity["iss"]
    assert identity["azp"] == keycloak.client_name
    assert float(identity["exp"]) > now
    assert float(identity["iat"]) <= now
    assert auth_json["context"] == f"Bearer {auth.token.access_token}"
    assert realm_role["name"] in identity["realm_access"]["roles"]
    assert identity["email"] == keycloak.user.properties["email"]
