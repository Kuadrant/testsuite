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

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import logging
from testsuite.config import settings

from openshift_client import selector, OpenShiftPythonException

logger = logging.getLogger(__name__)


def collect_pod_logs(
    cluster,
    namespace: str,
    label_selector: dict,
    log_dir: Path,
    start_time: datetime,
    component_name: str,
    container_name: Optional[str] = None,
):
    """
    Collect logs from pods matching the label selector with time filtering.

    If container_name is specified, only collect logs from that container.
    Otherwise, collect logs from all containers in the pod.
    """
    since_time = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        target_cluster = cluster.change_project(namespace)
        with target_cluster.context:
            pods = selector("pod", labels=label_selector)

            if pods.count_existing() == 0:
                logger.warning(f"No {component_name} pods found with labels {label_selector} in namespace {namespace}")
                return

            for pod in pods.objects():
                pod_name = pod.name()

                try:
                    # Get container list
                    containers = [container_name] if container_name else [c.name for c in pod.model.spec.containers]

                    for container in containers:
                        try:
                            # Use oc logs command for better parameter support
                            result = subprocess.run(
                                [
                                    "oc",
                                    "logs",
                                    f"pod/{pod_name}",
                                    "-c",
                                    container,
                                    "-n",
                                    namespace,
                                    f"--since-time={since_time}",
                                    "--timestamps",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                            logs = result.stdout if result.returncode == 0 else result.stderr

                            # Save logs
                            log_file = log_dir / f"{component_name}-{pod_name}-{container}.log"
                            with open(log_file, "w") as f:
                                f.write(f"# Component: {component_name}\n")
                                f.write(f"# Pod: {pod_name}\n")
                                f.write(f"# Container: {container}\n")
                                f.write(f"# Namespace: {namespace}\n")
                                f.write(f"# Logs since: {since_time}\n")
                                f.write(f"# {'=' * 70}\n\n")
                                f.write(logs)

                            logger.info(f"Collected {component_name} logs: {pod_name}/{container}")

                        except subprocess.TimeoutExpired:
                            error_file = log_dir / f"{component_name}-{pod_name}-{container}-error.txt"
                            error_file.write_text("Timeout while collecting logs")
                            logger.error(f"Timeout collecting logs from {pod_name}/{container}")
                        except Exception as e:
                            error_file = log_dir / f"{component_name}-{pod_name}-{container}-error.txt"
                            error_file.write_text(f"Failed to collect logs: {e}")
                            logger.error(f"Failed to get logs from {pod_name}/{container}: {e}")

                except Exception as e:
                    error_file = log_dir / f"{component_name}-{pod_name}-error.txt"
                    error_file.write_text(f"Failed to process pod: {e}")
                    logger.error(f"Failed to process pod {pod_name}: {e}")

    except OpenShiftPythonException as e:
        logger.error(f"Failed to access {component_name} pods in namespace {namespace}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error collecting {component_name} logs: {e}")


def collect_authorino_logs(cluster, log_dir: Path, start_time: datetime, authorino):
    """Collect logs from Authorino pods"""
    try:
        authorino_name = authorino.name()
    except Exception:
        authorino_name = "authorino"

    # Try primary label selector
    label_selector = {"authorino-resource": authorino_name}

    # Check if pods exist with primary selector
    try:
        authorino_cluster = cluster.change_project("kuadrant-system")
        with authorino_cluster.context:
            pods = selector("pod", labels=label_selector)
            if pods.count_existing() == 0:
                # Fallback to alternative label
                label_selector = {"app": authorino_name}
    except Exception:
        pass

    collect_pod_logs(
        cluster=cluster,
        namespace="kuadrant-system",
        label_selector=label_selector,
        log_dir=log_dir,
        start_time=start_time,
        component_name="authorino",
    )


def collect_limitador_logs(cluster, log_dir: Path, start_time: datetime, limitador):
    """Collect logs from Limitador pods"""
    try:
        limitador_name = limitador.name()
    except Exception:
        limitador_name = "limitador"

    # Try primary label selector
    label_selector = {"app": "limitador"}

    # Check if we should use a more specific selector
    try:
        limitador_cluster = cluster.change_project("kuadrant-system")
        with limitador_cluster.context:
            pods = selector("pod", labels=label_selector)
            if pods.count_existing() == 0:
                # Fallback to resource-specific label
                label_selector = {"limitador-resource": limitador_name}
    except Exception:
        pass

    collect_pod_logs(
        cluster=cluster,
        namespace="kuadrant-system",
        label_selector=label_selector,
        log_dir=log_dir,
        start_time=start_time,
        component_name="limitador",
    )


def collect_dns_operator_logs(cluster, log_dir: Path, start_time: datetime):
    """Collect logs from DNS Operator"""
    collect_pod_logs(
        cluster=cluster,
        namespace="kuadrant-system",
        label_selector={"control-plane": "dns-operator-controller-manager"},
        log_dir=log_dir,
        start_time=start_time,
        component_name="dns-operator",
        container_name="manager",
    )


def collect_authorino_operator_logs(cluster, log_dir: Path, start_time: datetime):
    """Collect logs from Authorino Operator"""
    collect_pod_logs(
        cluster=cluster,
        namespace="kuadrant-system",
        label_selector={"control-plane": "authorino-operator"},
        log_dir=log_dir,
        start_time=start_time,
        component_name="authorino-operator",
        container_name="manager",
    )


def collect_kuadrant_operator_logs(cluster, log_dir: Path, start_time: datetime):
    """Collect logs from Kuadrant Operator"""
    collect_pod_logs(
        cluster=cluster,
        namespace="kuadrant-system",
        label_selector={"control-plane": "kuadrant-operator"},
        log_dir=log_dir,
        start_time=start_time,
        component_name="kuadrant-operator",
        container_name="manager",
    )


def collect_gateway_logs(cluster, log_dir: Path, start_time: datetime, gateway):
    """Collect logs from Gateway pods"""
    try:
        gateway_name = gateway.name()
        gateway_namespace = gateway.namespace()
    except Exception as e:
        print(f"  [FAIL] Could not get gateway name/namespace: {e}")
        return

    # Try primary label selector for Gateway API
    label_selector = {"gateway.networking.k8s.io/gateway-name": gateway_name}

    # Check if pods exist with primary selector
    try:
        with cluster.context:
            pods = selector("pod", labels=label_selector)
            if pods.count_existing() == 0:
                # Fallback to Istio label
                label_selector = {"istio.io/gateway-name": gateway_name}
    except Exception:
        pass

    collect_pod_logs(
        cluster=cluster,
        namespace=gateway_namespace,
        label_selector=label_selector,
        log_dir=log_dir,
        start_time=start_time,
        component_name="gateway",
    )


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
    except Exception:
        pass

    # Default: no logging
    return set()


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
        logger.info(f"No log components configured for {test_name} - skipping log collection")
        return

    # Create log directory
    log_dir = Path("test-failures") / worker_id / test_name
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Collecting logs for failed test: {test_name}")
    logger.info(f"Worker: {worker_id}")
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"Configured components: {', '.join(sorted(enabled_components))}")

    # Collect logs from available components
    # Check which fixtures are available in the test

    def should_collect(component_name):
        """Check if we should collect logs for this component"""
        return component_name in enabled_components

    # Authorino
    if should_collect("authorino"):
        try:
            logger.info("Collecting Authorino logs...")
            collect_pod_logs(
                cluster=cluster,
                namespace=settings["service_protection"]["system_project"],
                label_selector={"authorino-resource": "authorino"},
                log_dir=log_dir,
                start_time=start_time,
                component_name="authorino",
            )
        except Exception as e:
            logger.warning(f"Could not collect Authorino logs: {e}")

    # Limitador
    if should_collect("limitador"):
        try:
            logger.info("Collecting Limitador logs...")
            collect_pod_logs(
                cluster=cluster,
                namespace=settings["service_protection"]["system_project"],
                label_selector={"app": "limitador"},
                log_dir=log_dir,
                start_time=start_time,
                component_name="limitador",
            )
        except Exception as e:
            logger.warning(f"Could not collect Limitador logs: {e}")

    # DNS Operator
    if should_collect("dns-operator"):
        try:
            logger.info("Collecting DNS Operator logs...")
            collect_pod_logs(
                cluster=cluster,
                namespace=settings["service_protection"]["system_project"],
                label_selector={"control-plane": "dns-operator-controller-manager"},
                log_dir=log_dir,
                start_time=start_time,
                component_name="dns-operator",
            )
        except Exception as e:
            logger.warning(f"Could not collect DNS Operator logs: {e}")

    # Authorino Operator
    if should_collect("authorino-operator"):
        try:
            logger.info("Collecting Authorino Operator logs...")
            collect_pod_logs(
                cluster=cluster,
                namespace=settings["service_protection"]["system_project"],
                label_selector={"control-plane": "authorino-operator"},
                log_dir=log_dir,
                start_time=start_time,
                component_name="authorino-operator",
            )
        except Exception as e:
            logger.warning(f"Could not collect Authorino Operator logs: {e}")


    # Limitador Operator
    if should_collect("limitador-operator"):
        try:
            logger.info("Collecting Limitador Operator logs...")
            collect_pod_logs(
                cluster=cluster,
                namespace="kuadrant-system",
                label_selector={"app": "limitador-operator"},
                log_dir=log_dir,
                start_time=start_time,
                component_name="limitador-operator",
            )
        except Exception as e:
            logger.warning(f"Could not collect Limitador Operator logs: {e}")

    # Kuadrant Operator
    if should_collect("kuadrant-operator"):
        try:
            logger.info("Collecting Kuadrant Operator logs...")
            collect_kuadrant_operator_logs(cluster, log_dir, start_time)
        except Exception as e:
            logger.warning(f"Could not collect Kuadrant Operator logs: {e}")

    # Gateway
    if should_collect("gateway"):
        try:
            logger.info("Collecting Gateway logs...")
            gateway = item.funcargs.get("gateway")
            if gateway:
                gateway_name = gateway.name()
                gateway_namespace = gateway.namespace()
                
            collect_pod_logs(cluster, gateway_namespace, {"gateway.networking.k8s.io/gateway-name": gateway_name}, log_dir, start_time, "gateway")
        except Exception as e:
            logger.warning(f"Could not collect Gateway logs: {e}")

    logger.info(f"Log collection complete. Logs saved to: {log_dir}")
