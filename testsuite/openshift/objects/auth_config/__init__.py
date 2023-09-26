"""AuthConfig CR object"""
from functools import cached_property
from typing import Dict, List, Optional

from testsuite.objects import Rule, asdict
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from .sections import IdentitySection, MetadataSection, ResponseSection, AuthorizationSection


class AuthConfig(OpenShiftObject):
    """Represents AuthConfig CR from Authorino"""

    @property
    def auth_section(self):
        """Returns objects where all auth related things should be added"""
        return self.model.spec

    @cached_property
    def authorization(self) -> AuthorizationSection:
        """Gives access to authorization settings"""
        return AuthorizationSection(self, "authorization")

    @cached_property
    def identity(self) -> IdentitySection:
        """Gives access to identity settings"""
        return IdentitySection(self, "authentication")

    @cached_property
    def metadata(self) -> MetadataSection:
        """Gives access to metadata settings"""
        return MetadataSection(self, "metadata")

    @cached_property
    def responses(self) -> ResponseSection:
        """Gives access to response settings"""
        return ResponseSection(self, "response")

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name,
        route,
        labels: Dict[str, str] = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "authorino.kuadrant.io/v1beta2",
            "kind": "AuthConfig",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {"hosts": []},
        }
        obj = cls(model, context=openshift.context)
        route.add_auth_config(obj)
        return obj

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
    def add_rule(self, when: list[Rule]):
        """Add rule for the skip of entire AuthConfig"""
        self.auth_section.setdefault("when", [])
        self.auth_section["when"].extend([asdict(x) for x in when])
