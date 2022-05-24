"""Authorino CR object"""
from typing import Any, Dict

from openshift import APIObject

from testsuite.openshift.client import OpenShiftClient


class Authorino(APIObject):
    """Represents Authorino CR objects from Authorino-operator"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, image=None, cluster_wide=False):
        """Creates base instance"""
        model: Dict[str, Any] = {
            "apiVersion": "operator.authorino.kuadrant.io/v1beta1",
            "kind": "Authorino",
            "metadata": {
                "name": name,
                "namespace": openshift.project
            },
            "spec": {
                "clusterWide": cluster_wide,
                "listener": {
                    "tls": {
                        "enabled": False
                    }
                },
                "oidcServer": {
                    "tls": {
                        "enabled": False
                    }
                }
            }
        }
        if image:
            model["spec"]["image"] = image

        return cls(model, context=openshift.context)

    def commit(self):
        """
        Creates object on the server and returns created entity.
        It will be the same class but attributes might differ, due to server adding/rejecting some of them.
        """
        self.create(["--save-config=true"])
        return self.refresh()

    @property
    def authorization_url(self):
        """Return service endpoint for authorization"""
        return f"{self.name()}-authorino-authorization.{self.namespace()}.svc.cluster.local"
