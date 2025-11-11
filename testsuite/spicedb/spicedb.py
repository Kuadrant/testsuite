"""SpiceDB authorization service implementation"""

from dataclasses import dataclass
from typing import List
import backoff

from authzed.api.v1 import (
    InsecureClient,
    RelationshipUpdate,
    Relationship,
    ObjectReference,
    SubjectReference,
    RelationshipFilter,
    DeleteRelationshipsRequest,
    WriteSchemaRequest,
    WriteRelationshipsRequest,
    CheckPermissionRequest,
)

from testsuite.config import settings
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.lifecycle import LifecycleObject


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

    This class provides a high-level interface to interact with SpiceDB using the official
    Authzed Python client (https://github.com/authzed/authzed-py).
    """

    def __init__(self, server_url: str, token: str):
        self._client = InsecureClient(server_url, token)

    def create_schema(self, schema_config: SchemaConfig):
        """Write a schema defining objects, roles, and permissions in SpiceDB."""
        schema_str = f"""
        definition {schema_config.subject_type} {{}}
        definition {schema_config.resource_type} {{
            relation {schema_config.relation1}: {schema_config.subject_type}
            relation {schema_config.relation2}: {schema_config.subject_type}

            permission {schema_config.permission1} = {schema_config.relation1} + {schema_config.relation2}
            permission {schema_config.permission2} = {schema_config.relation2}
        }}
        """
        request = WriteSchemaRequest(schema=schema_str)
        response = self._client.WriteSchema(request)
        return response

    def create_relationship(self, relationship_config: RelationshipConfig):
        """Create relationships between subjects and a resource with given roles."""
        updates = []
        for relation, subject_id in zip(relationship_config.relations, relationship_config.subject_ids):
            updates.append(
                RelationshipUpdate(
                    operation=RelationshipUpdate.Operation.OPERATION_CREATE,
                    relationship=Relationship(
                        resource=ObjectReference(
                            object_type=relationship_config.resource_type, object_id=relationship_config.resource_id
                        ),
                        relation=relation,
                        subject=SubjectReference(
                            object=ObjectReference(object_type=relationship_config.subject_type, object_id=subject_id)
                        ),
                    ),
                )
            )
        request = WriteRelationshipsRequest(updates=updates)
        response = self._client.WriteRelationships(request)
        return response

    def clear_all_relationships(self, schema_config: SchemaConfig):
        """Delete all relationships for the specified resource type."""
        request = DeleteRelationshipsRequest(
            relationship_filter=RelationshipFilter(resource_type=schema_config.resource_type)
        )
        response = self._client.DeleteRelationships(request)
        return response

    @backoff.on_predicate(backoff.constant, lambda x: x is False, max_tries=3, interval=5, jitter=None)
    def wait_for_relationship(self, schema_config: SchemaConfig, relationship_config: RelationshipConfig):
        """Check if the relationships are ready for use in SpiceDB."""
        check_request = CheckPermissionRequest(
            resource=ObjectReference(
                object_type=relationship_config.resource_type, object_id=relationship_config.resource_id
            ),
            permission=schema_config.permission1,
            subject=SubjectReference(
                object=ObjectReference(
                    object_type=schema_config.subject_type, object_id=relationship_config.subject_ids[1]
                )
            ),
        )
        response = self._client.CheckPermission(check_request)
        return response.permissionship == response.PERMISSIONSHIP_HAS_PERMISSION


# pylint: disable=too-many-instance-attributes
class SpiceDB(LifecycleObject):
    """
    SpiceDB authorization service deployed in Kubernetes.

    This class handles the Kubernetes deployment and provides access to a SpiceDB client
    for managing schemas and relationships.
    """

    def __init__(self, cluster: KubernetesClient, name, label, image, preshared_key="secret", replicas=1) -> None:
        self.cluster = cluster
        self.name = name
        self.label = label
        self.replicas = replicas
        self.image = image
        self.preshared_key = preshared_key
        self.deployment = None
        self.service = None
        self._client = None

    @property
    def grpc_port(self):
        """Returns the gRPC port number"""
        return self.service.get_port("grpc").port

    @property
    def grpc_url(self):
        """Returns the external gRPC URL for SpiceDB"""
        return f"{self.service.external_ip}:{self.grpc_port}"

    @property
    def client(self):
        """Lazy-initialized SpiceDB client for managing schemas and relationships"""
        if self._client is None:
            self._client = SpiceDBClient(self.grpc_url, self.preshared_key)
        return self._client

    def commit(self):
        """Deploy SpiceDB to Kubernetes"""
        match_labels = {"app": self.label, "deployment": self.name}

        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="spicedb",
            image=self.image,
            ports={"grpc": 50051},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            command_args=[
                "serve",
                "--grpc-preshared-key",
                self.preshared_key,
            ],
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[
                ServicePort(name="grpc", port=50051, targetPort="grpc"),
            ],
            labels={"app": self.label},
            service_type="LoadBalancer",
        )
        self.service.commit()

    def delete(self):
        """Delete SpiceDB deployment and service from Kubernetes"""
        if self.deployment:
            self.deployment.delete()
        if self.service:
            self.service.delete()

    def wait_for_ready(self, timeout=60 * 5):
        """Waits until Deployment and Service is marked as ready"""
        self.deployment.wait_for_ready(timeout)
        self.service.wait_for_ready(timeout, settings["control_plane"]["slow_loadbalancers"])
