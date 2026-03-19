"""Conftest for control plane distributed tracing tests"""

import pytest
import openshift_client as oc

from testsuite.config import settings


@pytest.fixture(scope="module", autouse=True)
def require_tracing_enabled(cluster, skip_or_fail):
    """Skip or fail tests if control plane tracing is not enabled on kuadrant-operator"""
    namespace = settings["service_protection"]["system_project"]
    deployment_name = "kuadrant-operator-controller-manager"

    try:
        namespace_client = cluster.change_project(namespace)

        with namespace_client.context:
            deployment = oc.selector(f"deployment/{deployment_name}").object()

            if not deployment.exists():
                skip_or_fail(f"Deployment %s not found in namespace %s", deployment_name, namespace)

            selector_labels = deployment.model.spec.selector.matchLabels
            pods = oc.selector("pod", labels=dict(selector_labels)).objects()

            pods = [pod for pod in pods if "kuadrant-operator" in pod.name()]

            if not pods:
                skip_or_fail(f"No pods found for deployment %s", deployment_name)

            # Check if OTEL environment variables are configured
            env_vars = pods[0].model.spec.containers[0].env

            if not any("OTEL_" in env_var.get('name', '') for env_var in env_vars):
                skip_or_fail("Control plane tracing not enabled (no OTEL_* env vars on kuadrant-operator)")

    except (oc.OpenShiftPythonException, AttributeError, KeyError) as e:
        skip_or_fail(f"Failed to check control plane tracing configuration: {e}")