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
    def add_request_grpc_method(self, method: str, var: Optional[str] = None, predicate: Optional[str] = None):
        """Add a grpc_method request action that calls an upstream"""
        action: Dict = {"type": "grpc_method", "method": method}
        if var:
            action["var"] = var
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_request_deny(
        self,
        predicate: Optional[str] = None,
        with_status: Optional[int] = None,
        with_headers: Optional[str] = None,
        with_body: Optional[str] = None,
    ):
        """Add a deny request action"""
        action: Dict = {"type": "deny"}
        if predicate:
            action["predicate"] = predicate
        if with_status:
            action["withStatus"] = with_status
        if with_headers:
            action["withHeaders"] = with_headers
        if with_body:
            action["withBody"] = with_body
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_request_fail(self, log_message: str, predicate: Optional[str] = None):
        """Add a fail request action"""
        action: Dict = {"type": "fail", "logMessage": log_message}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_request_headers(self, headers: List[List[str]], predicate: Optional[str] = None):
        """Add an add_headers request action"""
        action: Dict = {"type": "add_headers", "headersToAdd": str(headers)}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("request", []).append(action)

    @modify
    def add_response_grpc_method(self, method: str, var: Optional[str] = None, predicate: Optional[str] = None):
        """Add a grpc_method response action that calls an upstream"""
        action: Dict = {"type": "grpc_method", "method": method}
        if var:
            action["var"] = var
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("response", []).append(action)

    @modify
    def add_response_deny(
        self,
        predicate: Optional[str] = None,
        with_status: Optional[int] = None,
        with_headers: Optional[str] = None,
        with_body: Optional[str] = None,
    ):
        """Add a deny response action"""
        action: Dict = {"type": "deny"}
        if predicate:
            action["predicate"] = predicate
        if with_status:
            action["withStatus"] = with_status
        if with_headers:
            action["withHeaders"] = with_headers
        if with_body:
            action["withBody"] = with_body
        self.model.spec.setdefault("response", []).append(action)

    @modify
    def add_response_fail(self, log_message: str, predicate: Optional[str] = None):
        """Add a fail response action"""
        action: Dict = {"type": "fail", "logMessage": log_message}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("response", []).append(action)

    @modify
    def add_response_headers(self, headers: List[List[str]], predicate: Optional[str] = None):
        """Add an add_headers response action"""
        action: Dict = {"type": "add_headers", "headersToAdd": str(headers)}
        if predicate:
            action["predicate"] = predicate
        self.model.spec.setdefault("response", []).append(action)
