"""Authorino CR object"""
from typing import Any, Dict, List

import openshift
from openshift import APIObject, selector

from testsuite.objects import Authorino
from testsuite.openshift.client import OpenShiftClient


class AuthorinoCR(APIObject, Authorino):
    """Represents Authorino CR objects from Authorino-operator"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, image=None,
                        cluster_wide=False, label_selectors: List[str] = None):
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

        if label_selectors:
            model["spec"]["authConfigLabelSelectors"] = ",".join(label_selectors)

        with openshift.context:
            return cls(model)

    def wait_for_ready(self):
        """Waits until Authorino CR reports ready status"""
        with openshift.timeout(90):
            success, _, _ = self.self_selector().until_all(
                success_func=lambda obj:
                len(obj.model.status.conditions) > 0 and all(x.status == "True" for x in obj.model.status.conditions)
            )
            assert success, "Authorino did got get ready in time"
            self.refresh()

    def commit(self):
        """
        Creates object on the server and returns created entity.
        It will be the same class but attributes might differ, due to server adding/rejecting some of them.
        """
        self.create(["--save-config=true"])
        return self.refresh()

    @property
    def deployment(self):
        """Returns Deployment object for this Authorino"""
        with self.context:
            return selector(f"deployment/{self.name()}").object()

    @property
    def authorization_url(self):
        """Return service endpoint for authorization"""
        return f"{self.name()}-authorino-authorization.{self.namespace()}.svc.cluster.local"
