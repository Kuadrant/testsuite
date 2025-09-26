"""
SpiceDB by AuthZed is an authorization-only database
inspired by Google Zanzibar, used for managing and checking fine-grained access permissions
through a schema-defined relationship model.
https://authzed.com/
Note: Authentication is not handled by SpiceDB and must be implemented separately. Therefore, this tests doesn't
cover authentication and are is only focused on authorization.
"""

import pytest
from dynaconf import ValidationError

from testsuite.spicedb.spicedb import SpiceDBService, SchemaConfig, RelationshipConfig
from testsuite.kubernetes.secret import Secret

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def schema_config():
    """Create schema config with custom data."""
    schema_config = SchemaConfig(
        subject_type="user",
        resource_type="document",
        permission1="read",
        permission2="write",
        relation1="reader",
        relation2="writer",
    )
    return schema_config


@pytest.fixture(scope="module")
def relationship_config():
    """Create relationship config with custom data."""
    relationship_config = RelationshipConfig(
        subject_type="user",
        resource_type="document",
        relations=["writer", "reader"],
        resource_id="document1",
        subject_ids=["admin", "some_user"],
    )
    return relationship_config


@pytest.fixture(scope="module")
def spicedb_info(testconfig, skip_or_fail):
    """
    Validates that only the 'spicedb' section of the test config is used,
    and returns the relevant configuration (e.g., URL, secret, etc.).
    """
    try:
        testconfig.validators.validate(only="spicedb")
    except (KeyError, ValidationError) as exc:
        skip_or_fail(f"Spicedb configuration item is missing: {exc}")
    return testconfig["spicedb"]


@pytest.fixture(scope="module")
def create_secret(request, cluster, blame, spicedb_info, module_label, testconfig, kuadrant):
    """Create a secret for Authorino to use in authorization with SpiceDB. Secret mut be created in namespace where
    Authorino is deployed."""
    secret_name = blame("spicedb")
    if kuadrant:
        cluster = cluster.change_project(testconfig["service_protection"]["system_project"])
    secret = Secret.create_instance(
        cluster,
        secret_name,
        {"grpc-preshared-key": spicedb_info["password"]},
        labels={"app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret_name


@pytest.fixture(scope="module")
def spicedb(spicedb_info, schema_config):
    """
    Creates a SpiceDB service instance used for sending authorization requests.
    After the tests, it clears all relationships.
    """
    service = SpiceDBService(spicedb_info["url"], spicedb_info["password"])
    yield service
    service.clear_all_relationships(schema_config)


@pytest.fixture(scope="module")
def authorization(authorization, create_secret, spicedb_info, schema_config):
    """Clear all identity in the AuthConfig and add the spiceDB spec into authorization part."""
    authorization.identity.clear_all()
    authorization.authorization.add_spicedb(
        "spicedb-spicedb",
        spicedb_info["url"],
        create_secret,
        subject_type=schema_config.subject_type,
        resource_type=schema_config.resource_type,
        permission1=("GET", schema_config.permission1),
        permission2=("POST", schema_config.permission2),
        resource_selector="context.request.http.path." '@extract:{"sep":"/","pos":2}',
        subject_selector="context.request.http.headers.username",
    )
    return authorization


@pytest.fixture(scope="module", autouse=True)
def spicedb_query(spicedb, schema_config, relationship_config):
    """
    Prepares a test schema and sample relationships in SpiceDB for authorization tests.
    Check if the relationships are ready for authorization in SpiceDB.
    Returns the created schema and relationship objects for use in tests.
    """
    spicedb.create_schema(schema_config)
    spicedb.create_relationship(relationship_config)
    spicedb.wait_for_relationship(schema_config, relationship_config)


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
