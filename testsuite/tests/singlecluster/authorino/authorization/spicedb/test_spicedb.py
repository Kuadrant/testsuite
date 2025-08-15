"""
SpiceDB by AuthZed is an authorization-only database
inspired by Google Zanzibar, used for managing and checking fine-grained access permissions
through a schema-defined relationship model.
https://authzed.com/
Note: Authentication is not handled by SpiceDB and must be implemented separately. Therefore, this test doesn't
cover authentication and it is only focused on authorization.
"""

import pytest

from testsuite.spicedb.spicedb import SpiceDBService
from testsuite.kubernetes import KubernetesObject


pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def spicedb_info(testconfig):
    """
    Validates that only the 'spicedb' section of the test config is used,
    and returns the relevant configuration (e.g., URL, secret, etc.).
    """
    testconfig.validators.validate(only="spicedb")
    return testconfig["spicedb"]


@pytest.fixture(scope="module")
def create_client_secret(request, cluster, authorino):
    """Creates Client Secret, used by Authorino to start the authentication with the spiceDB"""

    def _create_secret(name, client_id, client_secret):
        model = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": authorino.namespace()},
            "stringData": {"clientID": client_id, "grpc-preshared-key": client_secret},
            "type": "Opaque",
        }
        secret = KubernetesObject(model, context=cluster.context)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret


@pytest.fixture(scope="module", autouse=True)
def client_secret(create_client_secret, blame, spicedb_info):
    """Creates the required secrets that will be used by Authorino to authenticate with spiceDB."""
    return create_client_secret(blame("spicedb-key"), "spicedb", spicedb_info["password"])


@pytest.fixture(scope="module")
def spicedb(spicedb_info):
    """
    Creates a SpiceDB service instance used for sending authorization requests.
    After the tests, it clears all relationships.
    """
    service = SpiceDBService(spicedb_info["url"], spicedb_info["password"])
    yield service
    service.clear_all_relationships(resource_type="document")


@pytest.fixture(scope="module")
def authorization(authorization, client_secret, spicedb_info):
    """Clear all identity in the AuthConfig and add the spiceDB spec into authorization part."""
    authorization.identity.clear_all()
    authorization.authorization.add_spicedb(
        "spicedb-spicedb",
        spicedb_info["url"],
        client_secret.name(),
        object1="user",
        object2="document",
        permission1=("GET", "read"),
        permission2=("POST", "write"),
    )
    return authorization


@pytest.fixture(scope="module", autouse=True)
def spicedb_query(spicedb):
    """
    Prepares a test schema and sample relationships in SpiceDB for authorization tests.
    Check if the relationships are ready for authorization in SpiceDB.
    Returns the created schema and relationship objects for use in tests.
    """
    schema = spicedb.create_schema("user", "document", "read", "write", "reader", "writer")
    relationship = spicedb.create_relationship(
        "user", "document", ["writer", "reader"], "document1", ["admin", "some_user"]
    )
    spicedb.wait_for_relationship("document", "document1", "read", "user", "some_user")
    return schema, relationship


def test_spicedb(client):
    """
    This test verifies that Authorino correctly queries SpiceDB for authorization decisions
    based on the defined schema and relationships.
    """

    response = client.get("/anything/document1", headers={"Username": "admin"})
    assert response is not None
    assert response.status_code == 200

    response = client.post("/anything/document1", headers={"Username": "admin"})
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/document1", headers={"Username": "some_user"})
    assert response is not None
    assert response.status_code == 200

    response = client.post("/anything/document1", headers={"Username": "some_user"})
    assert response is not None
    assert response.status_code == 403
