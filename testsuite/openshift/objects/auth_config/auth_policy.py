"""Module containing classes related to Auth Policy"""
from typing import Dict, List

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.gateway_api import HTTPRoute


class AuthPolicy(AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    def __init__(self, dict_to_model=None, string_to_model=None, context=None, route: HTTPRoute = None):
        super().__init__(dict_to_model, string_to_model, context)
        self._route = route

    @property
    def route(self) -> HTTPRoute:
        """Returns route to which the Policy is bound, won't work with objects fetched from Openshift"""
        if not self._route:
            # TODO: Fetch route from Openshift directly
            raise ValueError("This instance doesnt have a Route specified!!")
        return self._route

    @property
    def auth_section(self):
        return self.model.spec.setdefault("authScheme", {})

    # pylint: disable=unused-argument
    @classmethod
    def create_instance(  # type: ignore
        cls,
        openshift: OpenShiftClient,
        name,
        route: HTTPRoute,
        labels: Dict[str, str] = None,
        hostnames: List[str] = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1beta1",
            "kind": "AuthPolicy",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "targetRef": route.reference,
            },
        }

        return cls(model, context=openshift.context, route=route)

    def add_host(self, hostname):
        return self.route.add_hostname(hostname)

    def remove_host(self, hostname):
        return self.route.remove_hostname(hostname)

    def remove_all_hosts(self):
        return self.route.remove_all_hostnames()
