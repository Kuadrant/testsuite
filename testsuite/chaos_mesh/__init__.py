"""PodChaos object for simulating Pod faults in Kubernetes."""

from typing import Dict, List, Optional, Literal

from testsuite.kubernetes import KubernetesObject, modify
from testsuite.kubernetes.client import KubernetesClient


class PodChaos(KubernetesObject):
    """Represents PodChaos CR from Chaos Mesh."""

    ACTIONS = Literal["pod-failure", "pod-kill", "container-kill"]
    MODES = Literal["one", "all", "fixed", "fixed-percent", "random-max-percent"]

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        namespace: str = "kuadrant-system",
        labels: Optional[Dict[str, str]] = None,
    ):
        """Creates base instance."""
        model = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "metadata": {"name": name, "namespace": namespace, "labels": labels or {}},
            "spec": {"selector": {"labelSelectors": {}}},
        }
        return cls(model, context=cluster.context)

    @modify
    def set_action(self, action: ACTIONS):
        """Set the chaos action."""
        self.model.spec.action = action

    @modify
    def set_mode(self, mode: MODES, value: Optional[str] = None):
        """Set the experiment mode."""
        self.model.spec.mode = mode
        if value is not None:
            self.model.spec.value = value

    @modify
    def set_selector(self, labels: Dict[str, str], namespaces: Optional[List[str]] = None):
        """Set pod selector."""
        self.model.spec.selector.labelSelectors = labels
        if namespaces:
            self.model.spec.selector.namespaces = namespaces

    @modify
    def set_container_names(self, containers: List[str]):
        """Set target container names."""
        self.model.spec.containerNames = containers

    @modify
    def set_grace_period(self, period: int):
        """Set grace period for pod-kill action."""
        self.model.spec.gracePeriod = period

    @modify
    def set_duration(self, duration: str):
        """Set experiment duration."""
        self.model.spec.duration = duration

    def pod_failure(
        self,
        labels: Dict[str, str],
        duration: str,
        mode: MODES = "one",
        value: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
    ):
        """Configure for pod-failure chaos experiment."""
        self.set_action("pod-failure")
        self.set_mode(mode, value)
        self.set_selector(labels, namespaces)
        self.set_duration(duration)

    def pod_kill(
        self,
        labels: Dict[str, str],
        mode: MODES = "one",
        value: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
        grace_period: int = 0,
    ):
        """Configure for pod-kill chaos experiment."""
        self.set_action("pod-kill")
        self.set_mode(mode, value)
        self.set_selector(labels, namespaces)
        if grace_period > 0:
            self.set_grace_period(grace_period)

    def container_kill(
        self,
        labels: Dict[str, str],
        containers: List[str],
        mode: MODES = "one",
        value: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
    ):
        """Configure for container-kill chaos experiment."""
        self.set_action("container-kill")
        self.set_mode(mode, value)
        self.set_selector(labels, namespaces)
        self.set_container_names(containers)
