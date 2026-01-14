"""Module containing classes related to PlanPolicy"""

from typing import Dict, Any
from dataclasses import dataclass

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict


@dataclass
class Plan:
    """Plan dataclass for PlanPolicy"""

    tier: str
    predicate: str
    limits: Dict[str, Any]


class PlanPolicy(Policy):
    """PlanPolicy object, used for applying plan-based policies to a Gateway/HTTPRoute"""

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
            "kind": "PlanPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @modify
    def add_plan(self, plan: Plan):
        """Add a plan to the PlanPolicy"""
        self.model.spec.setdefault("plans", []).append(asdict(plan))
