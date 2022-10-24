"""AuthConfig CR object"""
from functools import cached_property
from typing import Dict

from testsuite.objects import Authorization, Responses, Metadata, Identities, Authorizations
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from testsuite.openshift.objects.auth_config.sections import AuthorizationsSection, IdentitySection, MetadataSection, \
    ResponsesSection


class AuthConfig(OpenShiftObject, Authorization):
    """Represents AuthConfig CR from Authorino"""

    @cached_property
    def authorization(self) -> Authorizations:
        return AuthorizationsSection(self, "authorization")

    @cached_property
    def identity(self) -> Identities:
        return IdentitySection(self, "identity")

    @cached_property
    def metadata(self) -> Metadata:
        return MetadataSection(self, "metadata")

    @cached_property
    def responses(self) -> Responses:
        return ResponsesSection(self, "response")

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, host, labels: Dict[str, str] = None):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "authorino.kuadrant.io/v1beta1",
            "kind": "AuthConfig",
            "metadata": {
                "name": name,
                "namespace": openshift.project
            },
            "spec": {
                "hosts": [host]
            }
        }

        if labels is not None:
            model["metadata"]["labels"] = labels

        return cls(model, context=openshift.context)

    @modify
    def add_host(self, hostname):
        self.model.spec.hosts.append(hostname)

    @modify
    def remove_host(self, hostname):
        self.model.spec.hosts.remove(hostname)

    @modify
    def remove_all_hosts(self):
        self.model.spec.hosts = []


    @modify
    def set_deny_with(self, code, value):
        """Set denyWith to authconfig"""
        self.model.spec["denyWith"] = {
            "unauthenticated": {"code": code, "headers": [{"name": "Location", "valueFrom": {"authJSON": value}}]}}
