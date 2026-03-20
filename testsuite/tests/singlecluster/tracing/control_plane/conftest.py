"""Shared fixtures for control plane distributed tracing tests."""

import pytest
import openshift_client as oc

from testsuite.config import settings
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes import Selector


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


@pytest.fixture(scope="module")
def auth_traces(authorization, tracing):
    """Fetches and validates traces for AuthPolicy."""
    traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(traces) > 0, f"No traces found for AuthPolicy: {authorization.name()}"
    return traces


@pytest.fixture(scope="module")
def rl_traces(rate_limit, tracing):
    """Fetches and validates traces for RateLimitPolicy."""
    traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": rate_limit.name()})
    assert len(traces) > 0, f"No traces found for RateLimitPolicy: {rate_limit.name()}"
    return traces


@pytest.fixture(scope="module")
def auth_policy_spans(auth_traces, authorization):
    """Spans with AuthPolicy metadata."""
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                predicate=lambda s: s.has_tag("policy.kind", "AuthPolicy")
                and s.has_tag("policy.name", authorization.name())
            )
        )
    assert len(spans) > 0, "No AuthPolicy spans found with policy metadata"
    return spans


@pytest.fixture(scope="module")
def rl_policy_spans(rl_traces, rate_limit):
    """Spans with RateLimitPolicy metadata."""
    spans = []
    for trace in rl_traces:
        spans.extend(
            trace.filter_spans(
                predicate=lambda s: s.has_tag("policy.kind", "RateLimitPolicy")
                and s.has_tag("policy.name", rate_limit.name())
            )
        )
    assert len(spans) > 0, "No RateLimitPolicy spans found with policy metadata"
    return spans


@pytest.fixture(scope="module")
def auth_reconcile_spans(auth_traces):
    """controller.reconcile spans for AuthPolicy."""
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                operation_name="controller.reconcile",
                predicate=lambda s: s.has_tag("event_kinds", "AuthPolicy.kuadrant.io"),
            )
        )
    assert len(spans) > 0, "No controller.reconcile spans with AuthPolicy.kuadrant.io in event_kinds"
    return spans


@pytest.fixture(scope="module")
def rl_reconcile_spans(rl_traces):
    """controller.reconcile spans for RateLimitPolicy."""
    spans = []
    for trace in rl_traces:
        spans.extend(
            trace.filter_spans(
                operation_name="controller.reconcile",
                predicate=lambda s: s.has_tag("event_kinds", "RateLimitPolicy.kuadrant.io"),
            )
        )
    assert len(spans) > 0, "No controller.reconcile spans with RateLimitPolicy.kuadrant.io in event_kinds"
    return spans


@pytest.fixture(scope="module")
def auth_reconciler_spans(auth_traces):
    """Auth reconciler operation spans with meaningful duration."""
    min_duration_us = 50
    expected_ops = [
        "reconciler.auth_configs",
        "reconciler.istio_auth_cluster",
        "reconciler.authorino_istio_integration",
    ]

    operations_spans = {}
    for op_name in expected_ops:
        matching = []
        for trace in auth_traces:
            matching.extend(
                trace.filter_spans(operation_name=op_name, predicate=lambda s: s.duration > min_duration_us)
            )
        operations_spans[op_name] = matching

    return operations_spans


@pytest.fixture(scope="module")
def rl_reconciler_spans(rl_traces):
    """RateLimitPolicy reconciler operation spans with meaningful duration."""
    min_duration_us = 50
    expected_ops = [
        "reconciler.limitador_limits",
        "reconciler.istio_ratelimit_cluster",
        "workflow.limitador",
    ]

    operations_spans = {}
    for op_name in expected_ops:
        matching = []
        for trace in rl_traces:
            matching.extend(
                trace.filter_spans(operation_name=op_name, predicate=lambda s: s.duration > min_duration_us)
            )
        operations_spans[op_name] = matching

    return operations_spans


@pytest.fixture(scope="module")
def auth_wasm_spans(auth_traces):
    """WASM-related spans from auth traces with meaningful duration."""
    min_duration_us = 50
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                predicate=lambda s: ("wasm." in s.operation_name or "istio_extension" in s.operation_name)
                and s.duration > min_duration_us
            )
        )
    return spans


@pytest.fixture(scope="module")
def rl_wasm_spans(rl_traces):
    """WASM-related spans from rl traces with meaningful duration."""
    min_duration_us = 50
    spans = []
    for trace in rl_traces:
        spans.extend(
            trace.filter_spans(
                predicate=lambda s: ("wasm." in s.operation_name or "istio_extension" in s.operation_name)
                and s.duration > min_duration_us
            )
        )
    return spans

