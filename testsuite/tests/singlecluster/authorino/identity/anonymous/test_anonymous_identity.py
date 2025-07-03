"""Test for anonymous identity"""

import pytest


pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add Keycloak identity"""
    authorization.identity.add_oidc("keycloak", keycloak.well_known["issuer"])
    return authorization


def test_anonymous_identity(client, auth, authorization):
    """
    Setup:
        - Create AuthConfig with Keycloak identity
    Test:
        - Send request with authentication
        - Assert that response status code is 200
        - Send request without authentication
        - Assert that response status code is 401 (Unauthorized)
        - Add anonymous identity
        - Send request without authentication
        - Assert that response status code is 200
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get")
    assert response.status_code == 401

    authorization.identity.add_anonymous("anonymous")
    authorization.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
