"""
SpiceDB by AuthZed is an authorization-only database
inspired by Google Zanzibar, used for managing and checking fine-grained access permissions
through a schema-defined relationship model.
https://authzed.com/
Note: Authentication is not handled by SpiceDB and must be implemented separately. Therefore, these tests don't
cover authentication and are only focused on authorization.
"""

import pytest
import grpc

from testsuite.kubernetes.secret import Secret
from testsuite.spicedb.spicedb import SpiceDB, SchemaConfig, RelationshipConfig

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def schema_config():
    """Create schema config with custom data."""
    return SchemaConfig(
        subject_type="user",
        resource_type="document",
        permission1="read",
        permission2="write",
        relation1="reader",
        relation2="writer",
    )


@pytest.fixture(scope="module")
def relationship_config():
    """Create relationship config with custom data."""
    return RelationshipConfig(
        subject_type="user",
        resource_type="document",
        relations=["writer", "reader"],
        resource_id="document1",
        subject_ids=["admin", "some_user"],
    )


@pytest.fixture(scope="module")
def spicedb(request, cluster, blame, module_label, testconfig):
    """
    Deploy SpiceDB instance and manage its lifecycle.
    After the tests, it clears all relationships.
    """
    spicedb = SpiceDB(
        cluster,
        blame("spicedb"),
        module_label,
        image=testconfig["spicedb"]["image"],
    )
    request.addfinalizer(spicedb.delete)
    spicedb.commit()
    spicedb.wait_for_ready()

    yield spicedb


@pytest.fixture(scope="module")
def secret_name(request, cluster, module_label, kuadrant, blame, testconfig, spicedb):
    """
    Creates a secret containing the SpiceDB preshared key for Authorino to use.
    The secret is created in Authorino's namespace.
    """
    secret_name = blame("spicedb")
    if kuadrant:
        cluster = cluster.change_project(testconfig["service_protection"]["system_project"])
    secret = Secret.create_instance(
        cluster,
        secret_name,
        stringData={"grpc-preshared-key": spicedb.preshared_key},
        labels={"app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret_name


@pytest.fixture(scope="module", autouse=True)
def spicedb_query(spicedb, schema_config, relationship_config):
    """
    Prepares a test schema and sample relationships in SpiceDB for authorization tests.
    Checks if the relationships are ready for authorization in SpiceDB.

    If SpiceDB is unavailable (GRPC UNAVAILABLE error), the test is skipped instead of failing.
    This handles cases where the LoadBalancer external IP is not accessible due to infrastructure
    limitations in OpenStack environments, where the floating IP may not be routable despite being
    provisioned and active.
    """
    try:
        spicedb.client.create_schema(schema_config)
        spicedb.client.create_relationship(relationship_config)
        spicedb.client.wait_for_relationship(schema_config, relationship_config)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.UNAVAILABLE:  # pylint: disable=no-member
            pytest.skip(
                f"SpiceDB connection unavailable due to load balancer issues: {e.details()}"
            )  # pylint: disable=no-member
        raise


@pytest.fixture(scope="module")
def authorization(authorization, spicedb, schema_config, secret_name):
    """Clear all identity in the AuthConfig and add the SpiceDB spec into the authorization section."""
    authorization.identity.clear_all()
    authorization.authorization.add_spicedb(
        "spicedb-spicedb",
        spicedb.grpc_url,
        secret_name,
        subject_type=schema_config.subject_type,
        resource_type=schema_config.resource_type,
        permission1=("GET", schema_config.permission1),
        permission2=("POST", schema_config.permission2),
        resource_selector="context.request.http.path." '@extract:{"sep":"/","pos":2}',
        subject_selector="context.request.http.headers.username",
    )
    return authorization


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
