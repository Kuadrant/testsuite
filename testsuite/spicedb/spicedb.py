"""Module for interacting with SpiceDB to manage object schemas, roles, permissions,
and access control relationships."""

from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse
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

import backoff


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


class SpiceDBService:
    """
    This class provides methods to connect to a SpiceDB instance and perform
    schema and relationship operations. IT provides a high-level interface to
    interact with SpiceDB using the official Authzed Python client
    (https://github.com/authzed/authzed-py).
    """

    def __init__(self, server_url: str, token):
        self.client = InsecureClient(urlparse(server_url).netloc, token)

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
        response = self.client.WriteSchema(request)
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
        response = self.client.WriteRelationships(request)
        return response

    def clear_all_relationships(self, schema_config: SchemaConfig):
        """Delete all relationships for the specified resource type."""
        request = DeleteRelationshipsRequest(
            relationship_filter=RelationshipFilter(resource_type=schema_config.resource_type)
        )
        response = self.client.DeleteRelationships(request)
        return response

    @backoff.on_predicate(backoff.constant, lambda x: x is False, max_tries=5, interval=3)
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
        response = self.client.CheckPermission(check_request)
        return response.permissionship == response.PERMISSIONSHIP_HAS_PERMISSION
