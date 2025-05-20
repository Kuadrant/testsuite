"""Test for anonymous identity"""

import logging

import pytest

from testsuite.kuadrant.policy import has_observed_generation

pytestmark = [pytest.mark.authorino]

logger = logging.getLogger(__name__)


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

    generation = authorization.generation
    authorization.identity.add_anonymous("anonymous")
    authorization.wait_until(has_observed_generation(generation + 1))

    response = client.get("/get")
    assert response.status_code == 200
