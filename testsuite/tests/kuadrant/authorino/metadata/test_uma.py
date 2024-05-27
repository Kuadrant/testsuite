"""
Tests for resource-level authorization with User-Managed Access (UMA) resource registry.
https://github.com/Kuadrant/authorino/blob/main/docs/features.md#user-managed-access-uma-resource-registry-metadatauma
Test setup consists of:
    1. Add metadata UMA feature to the AuthConfig
    2. Add OPA policy that handles resource-level authorization
    3. Create 2 resources in Keycloak. One (`/anything/1`) owned by default Keycloak user
    4. Create new Keycloak user that should not have access to the `/anything/1` resource
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth

pytestmark = [pytest.mark.authorino]

VALIDATE_RESOURCE_OWNER = """
metadata := object.get(input.auth.metadata, "resource-data", [])[0]

allow {
  uma := object.get(metadata, "ownerManagedAccess", "")
  uma == false
}

allow {
  resource_owner := object.get(object.get(metadata, "owner", {}), "id", "")
  resource_owner == input.auth.identity.sub
}
"""


@pytest.fixture(scope="module", autouse=True)
def client_secret(create_client_secret, keycloak, blame):
    """Creates a required secret, used by Authorino to start the authentication with the UMA registry."""
    return create_client_secret(blame("uma-client-secret"), keycloak.client.auth_id, keycloak.client.secret)


@pytest.fixture(scope="module")
def auth2(keycloak, blame):
    """Creates new Keycloak User and returns his authentication object for HTTPX"""
    user = keycloak.realm.create_user(blame("newTestUser"), "p")
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def authorization(client_secret, authorization, keycloak, client, blame):
    # pylint: disable=unused-argument
    """
    Adds UMA resource-level authorization metadata feature and OPA policy that authorize user access to the resource.
    Creates two client resources on Keycloak client:
        1. `/anything` - accessed by anyone, not enforcing UMA
        2. `/anything/1` - accessed only by default Keycloak user (username = `keycloak.test_username`).
    """
    keycloak.client.create_uma_resource(blame("anything"), ["/anything"])
    keycloak.client.create_uma_resource(blame("anything1"), ["/anything/1"], keycloak.test_username)
    # Sometimes RHSSO does not instantly propagate new resources.
    # To prevent the flakiness of these tests, we are adding a new retry code: 404
    client.add_retry_code(404)

    authorization.metadata.add_uma("resource-data", keycloak.well_known["issuer"], client_secret.name())
    authorization.authorization.add_opa_policy("opa", VALIDATE_RESOURCE_OWNER)
    return authorization


def test_uma_resource_authorized(client, auth):
    """Test correct auth for default Keycloak user for both endpoints"""
    response = client.get("/anything", auth=auth)
    assert response.status_code == 200
    response = client.get("/anything/1", auth=auth)
    assert response.status_code == 200


def test_uma_resource_forbidden(client, auth2):
    """Test incorrect access for new user for resource that is owned by another user"""
    response = client.get("/anything", auth=auth2)
    assert response.status_code == 200
    response = client.get("/anything/1", auth=auth2)
    assert response.status_code == 403
