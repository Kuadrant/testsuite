"""Module containing classes related to TelemetryPolicy"""

from typing import Dict

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy


class TelemetryPolicy(Policy):
    """TelemetryPolicy for configuring telemetry metrics labels"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        target: Referencable,
        labels: Dict[str, str] = None,
        section_name: str = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "extensions.kuadrant.io/v1alpha1",
            "kind": "TelemetryPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @modify
    def add_label(self, label_name, label_path):
        """Add a label to the TelemetryPolicy"""
        metrics = self.model.spec.setdefault("metrics", {})
        default = metrics.setdefault("default", {})
        labels = default.setdefault("labels", {})
        labels[label_name] = label_path
