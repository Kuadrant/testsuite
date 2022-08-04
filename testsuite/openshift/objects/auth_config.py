"""AuthConfig CR object"""
from typing import Dict

from testsuite.objects import Authorization
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify


class AuthConfig(OpenShiftObject, Authorization):
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
    def add_oidc_identity(self, name, endpoint):
        """Adds OIDC identity"""
        identities = self.model.spec.setdefault("identity", [])
        identities.append({
            "name": name,
            "oidc": {
                "endpoint": endpoint
            }
        })

    @modify
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

    @modify
    def remove_all_identities(self):
        """Removes all identities from AuthConfig"""
        identities = self.model.spec.setdefault("identity", [])
        identities.clear()
