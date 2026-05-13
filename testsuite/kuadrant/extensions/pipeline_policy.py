"""Module containing classes related to PipelinePolicy"""

from typing import Dict, List, Optional

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy


class PipelinePolicy(Policy):
    """PipelinePolicy for defining declarative action pipelines (request/response actions) on routes"""

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
            "kind": "PipelinePolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @modify
    def add_action_method(self, name: str, url: str, service: str, method: str, message_template: str):
        """Add a gRPC upstream action method definition"""
        self.model.spec.setdefault("actionMethods", []).append(
            {
                "name": name,
                "url": url,
                "service": service,
                "method": method,
                "messageTemplate": message_template,
            }
        )

    @modify
    def add_request_allow(self, intention: str, predicate: Optional[str] = None):
        """Add an allow request action with a CEL predicate"""
        action: Dict = {"type": "allow", "intention": intention}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_request_grpc_method(
        self,
        method: str,
        var: Optional[str] = None,
        intention: Optional[str] = None,
        predicate: Optional[str] = None,
    ):
        """Add a grpc_method request action that calls an upstream"""
        action: Dict = {"type": "grpc_method", "method": method}
        if var:
            action["var"] = var
        if intention:
            action["intention"] = intention
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_response_headers(self, headers: List[List[str]], predicate: Optional[str] = None):
        """Add an add_headers response action"""
        action: Dict = {"type": "add_headers", "headersToAdd": str(headers)}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("response", []).append(action)

    @modify
    def add_response_code(self, response_code: int, predicate: Optional[str] = None):
        """Add a with_response_code response action"""
        action: Dict = {"type": "with_response_code", "responseCode": response_code}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("response", []).append(action)
