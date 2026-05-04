"""Shared fixtures for control plane distributed tracing tests."""

import pytest
import openshift_client as oc

from testsuite.tracing.models import Trace


@pytest.fixture(scope="module", autouse=True)
def require_tracing_enabled(system_project, skip_or_fail):
    """Skip or fail tests if control plane tracing is not enabled on kuadrant-operator"""
    deployment_name = "kuadrant-operator-controller-manager"

    try:
        with system_project.context:
            deployment = oc.selector(f"deployment/{deployment_name}").object()

            if not deployment.exists():
                skip_or_fail(f"Deployment {deployment_name} not found in namespace {system_project.project}")

            selector_labels = deployment.model.spec.selector.matchLabels
            if not selector_labels:
                skip_or_fail(f"Deployment {deployment_name} uses matchExpressions instead of matchLabels")

            pods = oc.selector("pod", labels=dict(selector_labels)).objects()

            pods = [pod for pod in pods if "kuadrant-operator" in pod.name()]

            if not pods:
                skip_or_fail(f"No pods found for deployment {deployment_name}")

            pod = pods[0]
            containers = pod.model.spec.containers
            if not containers:
                skip_or_fail(f"No containers found in pod {pod.name()}")

            # Check if OTEL environment variables are configured across all containers
            has_otel = False
            for container in containers:
                env_vars = getattr(container, "env", None) or []
                if any(env_var.get("name", "").startswith("OTEL_") for env_var in env_vars):
                    has_otel = True
                    break

            if not has_otel:
                skip_or_fail("Control plane tracing not enabled (no OTEL_* env vars on kuadrant-operator)")

    except (oc.OpenShiftPythonException, AttributeError, KeyError) as e:
        skip_or_fail(f"Failed to check control plane tracing configuration: {e}")


@pytest.fixture(scope="module")
def auth_traces(authorization, tracing, skip_or_fail) -> list[Trace]:
    """
    Fetches and validates traces for AuthPolicy.
    """
    policy_name = authorization.name()
    query_tags = {"policy.name": policy_name}
    traces = tracing.get_traces(service="kuadrant-operator", tags=query_tags)
    if not traces:
        skip_or_fail(
            f"No traces found for AuthPolicy '{policy_name}'. "
            f"Queried service='kuadrant-operator' with tags={query_tags}. "
            "Check if control plane tracing is enabled and policy was reconciled."
        )
    return traces


@pytest.fixture(scope="module")
def rl_traces(rate_limit, tracing, skip_or_fail) -> list[Trace]:
    """
    Fetches and validates traces for RateLimitPolicy.
    """
    policy_name = rate_limit.name()
    query_tags = {"policy.name": policy_name}
    traces = tracing.get_traces(service="kuadrant-operator", tags=query_tags)
    if not traces:
        skip_or_fail(
            f"No traces found for RateLimitPolicy '{policy_name}'. "
            f"Queried service='kuadrant-operator' with tags={query_tags}. "
            "Check if control plane tracing is enabled and policy was reconciled."
        )
    return traces
