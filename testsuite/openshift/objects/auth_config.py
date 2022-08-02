"""AuthConfig CR object"""
from typing import Dict

from openshift import APIObject

from testsuite.objects import Authorization
from testsuite.openshift.client import OpenShiftClient


class AuthConfig(APIObject, Authorization):
    """Represents AuthConfig CR from Authorino"""

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

    def commit(self):
        """
        Creates object on the server and returns created entity.
        It will be the same class but attributes might differ, due to server adding/rejecting some of them.
        """
        self.create(["--save-config=true"])
        return self.refresh()

    def add_oidc_identity(self, name, endpoint):
        """Adds OIDC identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "oidc": {
                "endpoint": endpoint
            }
        })

    def add_api_key_identity(self, name, label):
        """Adds API Key identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "apiKey": {
                "labelSelectors": {
                    "group": label
                }
            },
            "credentials": {
                "in": "authorization_header",
                "keySelector": "APIKEY"
            }
        })
