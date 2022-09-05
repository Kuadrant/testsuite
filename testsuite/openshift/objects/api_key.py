"""API Key Secret CR object"""
import base64

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject


class APIKey(OpenShiftObject):
    """Represents API Key Secret CR for Authorino"""

    def __str__(self):
        return base64.b64decode(self.model.data["api_key"]).decode("utf-8")

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, label, api_key):
        """Creates base instance"""
        model = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": openshift.project,
                "labels": {
                    "authorino.kuadrant.io/managed-by": "authorino",
                    "group": label
                }
            },
            "stringData": {
                "api_key": api_key
            },
            "type": "Opaque"
        }

        return cls(model, context=openshift.context)
