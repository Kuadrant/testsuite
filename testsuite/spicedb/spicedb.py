"""SpiceDB authorization service implementation"""

from dataclasses import dataclass
from typing import List
import backoff
import httpx

from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort


@dataclass
class SchemaConfig:
    """
    Defines the configuration for a SpiceDB schema object.

    Attributes:
        subject_type (str): The type of the subject (e.g., 'user', 'group').
        resource_type (str): The type of the resource (e.g., 'document', 'folder').
        permission1 (str): The first permission to assign in the schema.
        permission2 (str): The second permission to assign in the schema.
        relation1 (str): The first relation between subject and resource.
        relation2 (str): The second relation between subject and resource.
    """

    subject_type: str
    resource_type: str
    permission1: str
    permission2: str
    relation1: str
    relation2: str


@dataclass
class RelationshipConfig:
    """
    Represents a set of relationships between subjects and resources in SpiceDB.

    Attributes:
        subject_type (str): The type of the subject (e.g., 'user', 'team').
        resource_type (str): The type of the resource being related (e.g., 'document', 'project').
        relations (List[str]): A list of relation names to apply (e.g., ['reader', 'writer']).
        resource_id (str): The identifier of the resource instance.
        subject_ids (List[str]): A list of subject identifiers linked to the resource.
    """

    subject_type: str
    resource_type: str
    relations: List[str]
    resource_id: str
    subject_ids: List[str]


class SpiceDBClient:
    """
    Client for interacting with SpiceDB to manage schemas, relationships, and permissions.
    This class uses the SpiceDB HTTP API.
    """

    def __init__(self, server_url: str, token: str):
        """
        Initialize HTTP client for SpiceDB.

        """
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.client = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def create_schema(self, schema_config: SchemaConfig):
        """
        Write a schema defining objects, roles, and permissions in SpiceDB via HTTP API.
        """
        schema_str = f"""
        definition {schema_config.subject_type} {{}}
        definition {schema_config.resource_type} {{
            relation {schema_config.relation1}: {schema_config.subject_type}
            relation {schema_config.relation2}: {schema_config.subject_type}

            permission {schema_config.permission1} = {schema_config.relation1} + {schema_config.relation2}
            permission {schema_config.permission2} = {schema_config.relation2}
        }}
        """
        response = self.client.post(
            "/v1/schema/write",
            json={"schema": schema_str},
        )
        response.raise_for_status()
        return response.json()

    def create_relationship(self, relationship_config: RelationshipConfig):
        """Create relationships between subjects and a resource with given roles via HTTP API."""
        updates = []
        for relation, subject_id in zip(relationship_config.relations, relationship_config.subject_ids):
            updates.append(
                {
                    "operation": "OPERATION_CREATE",
                    "relationship": {
                        "resource": {
                            "objectType": relationship_config.resource_type,
                            "objectId": relationship_config.resource_id,
                        },
                        "relation": relation,
                        "subject": {
                            "object": {
                                "objectType": relationship_config.subject_type,
                                "objectId": subject_id,
                            }
                        },
                    },
                }
            )

        response = self.client.post(
            "/v1/relationships/write",
            json={"updates": updates},
        )
        response.raise_for_status()
        return response.json()

    def clear_all_relationships(self, schema_config: SchemaConfig):
        """Delete all relationships for the specified resource type via HTTP API."""
        response = self.client.post(
            "/v1/relationships/delete",
            json={
                "relationshipFilter": {
                    "resourceType": schema_config.resource_type,
                }
            },
        )
        response.raise_for_status()
        return response.json()

    @backoff.on_predicate(
        backoff.constant,
        lambda x: x is False,
        max_tries=3,
        interval=5,
        jitter=None,
        on_giveup=lambda details: (_ for _ in ()).throw(
            TimeoutError(f"SpiceDB relationships not ready after {details['tries']} tries. ")
        ),
    )
    def wait_for_relationship(self, schema_config: SchemaConfig, relationship_config: RelationshipConfig):
        """
        Check if the relationships are ready for use in SpiceDB via HTTP API.
        Raises TimeoutError if relationships are not ready after retries.
        """
        response = self.client.post(
            "/v1/permissions/check",
            json={
                "resource": {
                    "objectType": relationship_config.resource_type,
                    "objectId": relationship_config.resource_id,
                },
                "permission": schema_config.permission1,
                "subject": {
                    "object": {
                        "objectType": schema_config.subject_type,
                        "objectId": relationship_config.subject_ids[1],
                    }
                },
            },
        )
        response.raise_for_status()
        result = response.json()
        return result.get("permissionship") == "PERMISSIONSHIP_HAS_PERMISSION"


class SpiceDB(Backend):
    """
    SpiceDB authorization service deployed in Kubernetes.

    This class handles the Kubernetes deployment and provides access to a SpiceDB client
    for managing schemas and relationships.
    """

    def __init__(
        self, cluster: KubernetesClient, name: str, label: str, image: str, preshared_key="secret", replicas=1
    ) -> None:
        super().__init__(cluster, name, label)
        self.replicas = replicas
        self.image = image
        self.preshared_key = preshared_key
        self._client: SpiceDBClient | None = None
        self._http_url: str | None = None

    @property
    def grpc_port(self):
        """Returns the gRPC port number"""
        return self.service.get_port("grpc").port

    def set_http_url(self, http_url: str):
        """
        Set the HTTP URL for accessing SpiceDB externally via OpenShift Route.
        """
        self._http_url = http_url

    @property
    def http_url(self):
        """
        Returns the HTTP API URL for SpiceDB client (test suite access via OpenShift Route).
        """
        return self._http_url

    @property
    def grpc_url(self):
        """
        Returns the internal cluster DNS with gRPC port for pod-to-pod communication.
        """
        return f"{self.url}:{self.grpc_port}"

    @property
    def client(self):
        """
        Lazy-initialized SpiceDB client for managing schemas and relationships.
        Uses HTTP API for external access (test suite via OpenShift Route).
        """
        if self._client is None:
            self._client = SpiceDBClient(self.http_url, self.preshared_key)
        return self._client

    def commit(self):
        """Deploy SpiceDB to Kubernetes"""
        match_labels = {"app": self.label, "deployment": self.name}

        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="spicedb",
            image=self.image,
            ports={"grpc": 50051, "http": 8443},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            command_args=[
                "serve",
                "--grpc-preshared-key",
                self.preshared_key,
            ],
        )
        env_vars = self.deployment.container.setdefault("env", [])
        env_vars.append({"name": "SPICEDB_HTTP_ENABLED", "value": "true"})
        env_vars.append({"name": "SPICEDB_LOG_LEVEL", "value": "debug"})
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[
                ServicePort(name="grpc", port=50051, targetPort="grpc"),
                ServicePort(name="http", port=8443, targetPort="http"),
            ],
            labels={"app": self.label},
        )
        self.service.commit()

    def wait_for_ready(self, timeout=60 * 5):
        """Waits until Deployment is marked as ready"""
        self.deployment.wait_for_ready(timeout)
