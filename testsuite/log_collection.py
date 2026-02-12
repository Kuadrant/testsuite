"""
Generic log collection utilities for test failures

This module provides automatic log collection for failed tests across all test suites,
including support for parallel test execution with pytest-xdist.

Configuration:
--------------
Configure which components to collect logs from by adding a module-level
variable to your conftest.py:

   log_components = ["authorino", "gateway", "limitador"]

If not configured, no logs will be collected (opt-in by default).

Available components:
- authorino: Authorino service logs
- limitador: Limitador service logs
- gateway: Gateway/Istio proxy logs
- dns-operator: DNS Operator controller logs
- authorino-operator: Authorino Operator controller logs
- kuadrant-operator: Kuadrant Operator controller logs
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from openshift_client import selector, OpenShiftPythonException

from testsuite.config import settings

logger = logging.getLogger(__name__)


class LogCollector:
    """Generic log collector for Kubernetes pods."""

    def __init__(self, cluster, log_dir: Path, since_time: str):
        """
        Initialize the log collector.

        cluster: Kubernetes cluster client
        log_dir: Directory to save logs to
        since_time: ISO 8601 timestamp string (e.g., "2025-10-23T10:30:00Z")
        """
        self.cluster = cluster
        self.log_dir = log_dir
        self.since_time = since_time

    def collect_logs(
        self, namespace: str, label_selector: dict, component_name: str, container_name: Optional[str] = None
    ):
        """
        Collect logs from pods matching the given criteria.

        namespace: Kubernetes namespace to search in
        label_selector: Dictionary of labels to match pods (e.g., {"app": "myapp"})
        component_name: Name to use in log filenames
        container_name: Optional specific container name. If None, collects from all containers.
        """
        try:
            target_cluster = self.cluster.change_project(namespace)
            with target_cluster.context:
                pods = selector("pod", labels=label_selector)

                if pods.count_existing() == 0:
                    logger.warning(
                        "No %s pods found with labels %s in namespace %s", component_name, label_selector, namespace
                    )
                    return

                for pod in pods.objects():
                    pod_name = pod.name()
                    try:
                        containers = [container_name] if container_name else [c.name for c in pod.model.spec.containers]
                        for container in containers:
                            self._collect_container_logs(pod_name, container, namespace, component_name)
                    except (AttributeError, KeyError) as e:
                        error_file = self.log_dir / f"{component_name}-{pod_name}-error.txt"
                        error_file.write_text(f"Failed to process pod: {e}")
                        logger.error("Failed to process pod %s: %s", pod_name, e)

        except OpenShiftPythonException as e:
            logger.error("Failed to access %s pods in namespace %s: %s", component_name, namespace, e)

    def _collect_container_logs(self, pod_name: str, container: str, namespace: str, component_name: str):
        """Collect logs from a single container."""
        try:
            logs = self._fetch_pod_logs(pod_name, container, namespace)
            log_file = self.log_dir / f"{component_name}-{pod_name}-{container}.log"
            self._save_log_file(log_file, component_name, pod_name, container, namespace, logs)
            logger.info("Collected %s logs: %s/%s", component_name, pod_name, container)
        except subprocess.TimeoutExpired:
            error_file = self.log_dir / f"{component_name}-{pod_name}-{container}-error.txt"
            error_file.write_text("Timeout while collecting logs")
            logger.error("Timeout collecting logs from %s/%s", pod_name, container)
        except (OSError, IOError) as e:
            error_file = self.log_dir / f"{component_name}-{pod_name}-{container}-error.txt"
            error_file.write_text(f"Failed to collect logs: {e}")
            logger.error("Failed to get logs from %s/%s: %s", pod_name, container, e)

    def _fetch_pod_logs(self, pod_name: str, container: str, namespace: str) -> str:
        """Fetch logs from a specific pod container using oc logs command."""
        result = subprocess.run(
            [
                "oc",
                "logs",
                f"pod/{pod_name}",
                "-c",
                container,
                "-n",
                namespace,
                f"--since-time={self.since_time}",
                "--timestamps",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout if result.returncode == 0 else result.stderr

    def _save_log_file(
        self, log_file: Path, component_name: str, pod_name: str, container: str, namespace: str, logs: str
    ):
        """Save collected logs to a file with metadata header."""
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# Component: {component_name}\n")
            f.write(f"# Pod: {pod_name}\n")
            f.write(f"# Container: {container}\n")
            f.write(f"# Namespace: {namespace}\n")
            f.write(f"# Logs since: {self.since_time}\n")
            f.write(f"# {'=' * 70}\n\n")
            f.write(logs)


def get_log_components(item):
    """
    Determine which components to collect logs from based on module configuration.

    Walks up the test hierarchy looking for log_components configuration.
    Checks: test module -> parent conftest modules

    Returns a set of component names to collect logs from.
    If not configured, returns empty set (no logging).
    """
    # Check the test module itself first
    if hasattr(item.module, "log_components"):
        return set(item.module.log_components)

    # Get conftest modules from pytest's pluginmanager
    # Walk up the directory tree to find conftest modules with log_components
    try:
        if hasattr(item.config, "pluginmanager"):
            for plugin in item.config.pluginmanager.get_plugins():
                if hasattr(plugin, "__name__") and "conftest" in getattr(plugin, "__name__", ""):
                    if hasattr(plugin, "log_components"):
                        return set(plugin.log_components)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Default: no logging
    return set()


def _collect_component_logs(collector: LogCollector, component: str, system_namespace: str, gateway=None):
    """
    Collect logs for a specific component using the generic LogCollector.

    This function contains the knowledge of how to find each component's pods.
    """
    if component == "gateway" and gateway:
        try:
            logger.info("Collecting Gateway logs...")
            gateway_name = gateway.name()
            gateway_namespace = gateway.namespace()
            collector.collect_logs(
                gateway_namespace, {"gateway.networking.k8s.io/gateway-name": gateway_name}, "gateway"
            )
        except (AttributeError, KeyError, OpenShiftPythonException) as e:
            logger.warning("Could not collect Gateway logs: %s", e)
        return

    # Component configurations mapping
    if component == "authorino":
        namespace = system_namespace
        labels = {"authorino-resource": "authorino"}
        name = "authorino"
        container = None
    elif component == "limitador":
        namespace = system_namespace
        labels = {"app": "limitador"}
        name = "limitador"
        container = None
    elif component == "dns-operator":
        namespace = system_namespace
        labels = {"control-plane": "dns-operator-controller-manager"}
        name = "dns-operator"
        container = "manager"
    elif component == "authorino-operator":
        namespace = system_namespace
        labels = {"control-plane": "authorino-operator"}
        name = "authorino-operator"
        container = "manager"
    elif component == "limitador-operator":
        namespace = system_namespace
        labels = {"app": "limitador-operator"}
        name = "limitador-operator"
        container = "manager"
    elif component == "kuadrant-operator":
        namespace = system_namespace
        labels = {"control-plane": "kuadrant-operator"}
        name = "kuadrant-operator"
        container = "manager"
    else:
        return

    try:
        logger.info("Collecting %s logs...", component)
        collector.collect_logs(namespace, labels, name, container)
    except (OpenShiftPythonException, OSError, IOError, KeyError) as e:
        logger.warning("Could not collect %s logs: %s", component, e)


def collect_failure_artifacts(item, cluster, start_time: datetime):
    """
    Collect logs from configured components when a test fails.

    This function inspects the test's fixtures and module configuration
    to determine which components are available and should be logged.
    """
    test_name = item.name
    worker_id = getattr(item.config, "workerinput", {}).get("workerid", "master")

    # Determine which components to collect logs from
    enabled_components = get_log_components(item)
    if not enabled_components:
        logger.info("No log components configured for %s - skipping log collection", test_name)
        return

    # Create log directory
    log_dir = Path("test-failures") / worker_id / test_name
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Collecting logs for failed test: %s", test_name)
    logger.info("Worker: %s", worker_id)
    logger.info("Log directory: %s", log_dir)
    logger.info("Configured components: %s", ", ".join(sorted(enabled_components)))

    # Create generic collector
    since_time = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    collector = LogCollector(cluster, log_dir, since_time)
    system_namespace = settings["service_protection"]["system_project"]

    # Collect logs for each enabled component
    gateway = item.funcargs.get("gateway")
    for component in enabled_components:
        _collect_component_logs(collector, component, system_namespace, gateway)

    logger.info("Log collection complete. Logs saved to: %s", log_dir)
