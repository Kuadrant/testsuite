"""AuthConfig CR object"""
from functools import cached_property
from typing import Dict

from testsuite.objects import Authorization, Responses, Metadata, Identities, Authorizations
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from .sections import AuthorizationsSection, IdentitySection, MetadataSection, \
    ResponsesSection


class AuthConfig(OpenShiftObject, Authorization):
    """Represents AuthConfig CR from Authorino"""

    @cached_property
    def authorization(self) -> Authorizations:
        """Gives access to authorization settings"""
        return AuthorizationsSection(self, "authorization")

    @cached_property
    def identity(self) -> Identities:
        """Gives access to identity settings"""
        return IdentitySection(self, "identity")

    @cached_property
    def metadata(self) -> Metadata:
        """Gives access to metadata settings"""
        return MetadataSection(self, "metadata")

    @cached_property
    def responses(self) -> Responses:
        """Gives access to response settings"""
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
        """Adds host"""
        self.model.spec.hosts.append(hostname)

    @modify
    def remove_host(self, hostname):
        """Remove host"""
        self.model.spec.hosts.remove(hostname)

    @modify
    def remove_all_hosts(self):
        """Remove all hosts"""
        self.model.spec.hosts = []

    @modify
    def set_deny_with(self, code, value):
        """Set denyWith"""
        self.model.spec["denyWith"] = {
            "unauthenticated": {
                "code": code,
                "headers": [{
                    "name": "Location",
                    "valueFrom": {
                        "authJSON": value
                    }
                }]
            }
        }
