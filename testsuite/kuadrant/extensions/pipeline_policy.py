"""Module containing classes related to PipelinePolicy"""

from __future__ import annotations

from functools import cached_property
from typing import Dict, List, Optional

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy


class ActionSection:
    """Section for request/response actions in a PipelinePolicy, mirrors ActionSpec from the Go API"""

    def __init__(self, obj: "PipelinePolicy", section_name: str) -> None:
        self.obj = obj
        self.section_name = section_name

    def modify_and_apply(self, modifier_func, retries=2, cmd_args=None):
        """Delegates modify_and_apply to the parent PipelinePolicy"""

        def _new_modifier(obj):
            modifier_func(ActionSection(obj, self.section_name))

        return self.obj.modify_and_apply(_new_modifier, retries, cmd_args)

    @property
    def committed(self):
        """Delegates committed check to the parent PipelinePolicy"""
        return self.obj.committed

    @property
    def section(self):
        """Returns the action list for this section"""
        return self.obj.model.spec.setdefault(self.section_name, [])

    @modify
    def add_grpc_method(self, method: str, var: Optional[str] = None, predicate: Optional[str] = None):
        """Add a grpc_method action that calls an upstream"""
        action: Dict = {"type": "grpc_method", "method": method}
        if var:
            action["var"] = var
        if predicate:
            action["predicate"] = predicate
        self.section.append(action)

    @modify
    def add_deny(
        self,
        predicate: Optional[str] = None,
        with_status: Optional[int] = None,
        with_headers: Optional[str] = None,
        with_body: Optional[str] = None,
    ):
        """Add a deny action"""
        action: Dict = {"type": "deny"}
        if predicate:
            action["predicate"] = predicate
        if with_status:
            action["withStatus"] = with_status
        if with_headers:
            action["withHeaders"] = with_headers
        if with_body:
            action["withBody"] = with_body
        self.section.append(action)

    @modify
    def add_fail(self, log_message: str, predicate: Optional[str] = None):
        """Add a fail action"""
        action: Dict = {"type": "fail", "logMessage": log_message}
        if predicate:
            action["predicate"] = predicate
        self.section.append(action)

    @modify
    def add_headers(self, headers: List[List[str]], predicate: Optional[str] = None):
        """Add an add_headers action"""
        action: Dict = {"type": "add_headers", "headersToAdd": str(headers)}
        if predicate:
            action["predicate"] = predicate
        self.section.append(action)


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

    @cached_property
    def on_http_request(self) -> ActionSection:
        """Gives access to request actions"""
        return ActionSection(self, "request")

    @cached_property
    def on_http_response(self) -> ActionSection:
        """Gives access to response actions"""
        return ActionSection(self, "response")

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
