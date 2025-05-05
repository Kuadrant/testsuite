"""Test for anonymous identity"""

import logging

import pytest

pytestmark = [pytest.mark.authorino]

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add Keycloak identity"""
    authorization.identity.add_oidc("keycloak", keycloak.well_known["issuer"])
    return authorization


def has_generation(generation):
    """Check expected generation is present in the object's definition"""

    def _check(obj):
        if obj.model.metadata.generation == generation:
            return True
        return False

    return _check


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

    generation = authorization.model.metadata.generation + 1
    authorization.identity.add_anonymous("anonymous")
    success = authorization.wait_until(has_generation(generation))
    assert success, "AuthPolicy did not increment the generation in due time"
    authorization.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
