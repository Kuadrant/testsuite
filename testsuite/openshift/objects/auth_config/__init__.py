"""AuthConfig CR object"""
from functools import cached_property
from typing import Dict, List

from testsuite.objects import Rule
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from .sections import Identities, Metadata, Responses, Authorizations
from ..route import Route


class AuthConfig(OpenShiftObject):
    """Represents AuthConfig CR from Authorino"""

    @property
    def auth_section(self):
        """Returns objects where all auth related things should be added"""
        return self.model.spec

    @cached_property
    def authorization(self) -> Authorizations:
        """Gives access to authorization settings"""
        return Authorizations(self, "authorization")

    @cached_property
    def identity(self) -> Identities:
        """Gives access to identity settings"""
        return Identities(self, "identity")

    @cached_property
    def metadata(self) -> Metadata:
        """Gives access to metadata settings"""
        return Metadata(self, "metadata")

    @cached_property
    def responses(self) -> Responses:
        """Gives access to response settings"""
        return Responses(self, "response")

    @classmethod
    def create_instance(
        cls, openshift: OpenShiftClient, name, route: Route, labels: Dict[str, str] = None, hostnames: List[str] = None
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "authorino.kuadrant.io/v1beta1",
            "kind": "AuthConfig",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {"hosts": hostnames or route.hostnames},
        }

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
        self.auth_section["denyWith"] = {
            "unauthenticated": {"code": code, "headers": [{"name": "Location", "valueFrom": {"authJSON": value}}]}
        }

    @modify
    def add_rule(self, when: list[Rule]):
        """Add rule for the skip of entire AuthConfig"""
        self.auth_section.setdefault("when", [])
        self.auth_section["when"].extend([vars(x) for x in when])
