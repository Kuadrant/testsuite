"""Service Account object for OpenShift"""

from testsuite.openshift import OpenShiftObject
from testsuite.openshift.client import OpenShiftClient


class ServiceAccount(OpenShiftObject):
    """Service account object for OpenShift"""

    def __init__(self, openshift: OpenShiftClient, model: dict):
        self.openshift = openshift
        super().__init__(model, context=openshift.context)

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name: str, labels: dict[str, str] = None):
        """Creates new instance of service account"""
        model = {
            "kind": "ServiceAccount",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
        }

        return cls(openshift, model)

    def get_auth_token(self, audiences: list[str] = None) -> str:
        """Requests and returns bound token for service account"""
        audiences_args = [f"--audience={a}" for a in audiences or []]
        return self.openshift.do_action("create", "token", self.name(), *audiences_args).out().strip()
