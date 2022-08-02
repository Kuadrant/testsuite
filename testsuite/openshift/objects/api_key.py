"""API Key Secret CR object"""

from openshift import APIObject

from testsuite.openshift.client import OpenShiftClient


class APIKey(APIObject):
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

    def commit(self):
        """
        Creates object on the server and returns created entity.
        It will be the same class but attributes might differ, due to server adding/rejecting some of them.
        """
        self.create(["--save-config=true"])
        return self.refresh()
