"""API Key Secret CR object"""

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject


class APIKey(OpenShiftObject):
    """Represents API Key Secret CR for Authorino"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, label, api_key_string):
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
                "api_key": api_key_string
            },
            "type": "Opaque"
        }

        return cls(model, context=openshift.context)
