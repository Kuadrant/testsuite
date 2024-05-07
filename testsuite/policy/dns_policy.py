"""Module for DNSPolicy related classes"""

import openshift_client as oc

from testsuite.gateway import Referencable
from testsuite.openshift import OpenShiftObject
from testsuite.openshift.client import OpenShiftClient
from testsuite.utils import has_condition


class DNSPolicy(OpenShiftObject):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        parent: Referencable,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {"targetRef": parent.reference, "routingStrategy": "simple"},
        }

        return cls(model, context=openshift.context)

    def wait_for_ready(self):
        """Wait for DNSPolicy to be Enforced"""
        with oc.timeout(90):
            success, _, _ = self.self_selector().until_all(
                success_func=has_condition("Enforced", "True"),
                tolerate_failures=5,
            )
            assert success, f"{self.kind()} did not get ready in time"
