"""Module for interacting with SpiceDB to manage object schemas, roles, permissions,
and access control relationships."""

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


class SpiceDBService:
    """
    This class provides methods to connect to a SpiceDB instance and perform
    schema and relationship operations. IT provides a high-level interface to
    interact with SpiceDB using the official Authzed Python client
    (https://github.com/authzed/authzed-py).
    """

    def __init__(self, server_url: str, token):
        self.client = InsecureClient(urlparse(server_url).netloc, token)

    def create_schema(self, object1: str, object2: str, permission1: str, permission2: str, role1: str, role2: str):
        """Write a schema defining objects, roles, and permissions in SpiceDB."""
        schema_str = (
            f"definition {object1} {{}}\n"
            f"definition {object2} {{\n"
            f"    relation {role1}: {object1}\n"
            f"    relation {role2}: {object1}\n\n"
            f"    permission {permission1} = {role1} + {role2}\n"
            f"    permission {permission2} = {role2}\n"
            f"}}"
        )
        request = WriteSchemaRequest(schema=schema_str)
        response = self.client.WriteSchema(request)
        return response

    def create_relationship(
        self, object1: str, object2: str, roles: list[str], object2_id: str, subject_ids: list[str]
    ):
        """Create relationships between subjects and a resource with given roles."""
        updates = []
        for role, subject_id in zip(roles, subject_ids):
            updates.append(
                RelationshipUpdate(
                    operation=RelationshipUpdate.Operation.OPERATION_CREATE,
                    relationship=Relationship(
                        resource=ObjectReference(object_type=object2, object_id=object2_id),
                        relation=role,
                        subject=SubjectReference(object=ObjectReference(object_type=object1, object_id=subject_id)),
                    ),
                )
            )
        request = WriteRelationshipsRequest(updates=updates)
        response = self.client.WriteRelationships(request)
        return response

    def clear_all_relationships(self, resource_type: str):
        """Delete all relationships for the specified resource type."""
        request = DeleteRelationshipsRequest(relationship_filter=RelationshipFilter(resource_type=resource_type))
        response = self.client.DeleteRelationships(request)
        return response

    def wait_for_relationship(self, resource_type, resource_id, permission, subject_type, subject_id):
        """Check if the relationships are ready for use in SpiceDB."""
        while True:
            check_request = CheckPermissionRequest(
                resource=ObjectReference(object_type=resource_type, object_id=resource_id),
                permission=permission,
                subject=SubjectReference(object=ObjectReference(object_type=subject_type, object_id=subject_id)),
            )
            response = self.client.CheckPermission(check_request)
            if response.permissionship == response.PERMISSIONSHIP_HAS_PERMISSION:
                return True
