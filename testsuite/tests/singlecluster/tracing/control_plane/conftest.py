"""Shared fixtures for control plane distributed tracing tests."""

import pytest
import openshift_client as oc

from testsuite.config import settings

from testsuite.tracing.models import Trace, Span

# Minimum span duration in microseconds to indicate actual work performed
MIN_MEANINGFUL_DURATION_US = 50


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
                skip_or_fail(f"No pods found for deployment {deployment_name}")

            pod = pods[0]
            containers = pod.model.spec.containers
            if not containers:
                skip_or_fail(f"No containers found in pod {pod.name()}")

            # Check if OTEL environment variables are configured
            env_vars = containers[0].env

            if not any("OTEL_" in env_var.get('name', '') for env_var in env_vars):
                skip_or_fail("Control plane tracing not enabled (no OTEL_* env vars on kuadrant-operator)")

    except (oc.OpenShiftPythonException, AttributeError, KeyError) as e:
        skip_or_fail(f"Failed to check control plane tracing configuration: {e}")


@pytest.fixture(scope="module")
def auth_traces(authorization, tracing) -> list[Trace]:
    """
    Fetches and validates traces for AuthPolicy.
    """
    policy_name = authorization.name()
    query_tags = {"policy.name": policy_name}
    traces = tracing.get_traces(service="kuadrant-operator", tags=query_tags)
    if len(traces) == 0:
        pytest.skip(
            f"No traces found for AuthPolicy '{policy_name}'. "
            f"Queried service='kuadrant-operator' with tags={query_tags}. "
            "Check if control plane tracing is enabled and policy was reconciled."
        )
    return traces


@pytest.fixture(scope="module")
def rl_traces(rate_limit, tracing) -> list[Trace]:
    """
    Fetches and validates traces for RateLimitPolicy.
    """
    policy_name = rate_limit.name()
    query_tags = {"policy.name": policy_name}
    traces = tracing.get_traces(service="kuadrant-operator", tags=query_tags)
    if len(traces) == 0:
        pytest.skip(
            f"No traces found for RateLimitPolicy '{policy_name}'. "
            f"Queried service='kuadrant-operator' with tags={query_tags}. "
            "Check if control plane tracing is enabled and policy was reconciled."
        )
    return traces


@pytest.fixture(scope="module")
def auth_policy_spans(auth_traces, authorization) -> list[Span]:
    """Spans with AuthPolicy metadata."""
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                lambda s: s.has_tag("policy.kind", "AuthPolicy")
                          and s.has_tag("policy.name", authorization.name())
            )
        )
    if len(spans) == 0:
        pytest.skip("No AuthPolicy spans found with policy metadata")
    return spans


@pytest.fixture(scope="module")
def rl_policy_spans(rl_traces, rate_limit) -> list[Span]:
    """Spans with RateLimitPolicy metadata."""
    spans = []
    for trace in rl_traces:
        spans.extend(
            trace.filter_spans(
                lambda s: s.has_tag("policy.kind", "RateLimitPolicy")
                          and s.has_tag("policy.name", rate_limit.name())
            )
        )
    if len(spans) == 0:
        pytest.skip("No RateLimitPolicy spans found with policy metadata")
    return spans


@pytest.fixture(scope="module")
def auth_reconcile_spans(auth_traces) -> list[Span]:
    """controller.reconcile spans for AuthPolicy."""
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile"
                          and s.has_tag("event_kinds", "AuthPolicy.kuadrant.io")
            )
        )
    if len(spans) == 0:
        pytest.skip("No controller.reconcile spans with AuthPolicy.kuadrant.io in event_kinds")
    return spans


@pytest.fixture(scope="module")
def rl_reconcile_spans(rl_traces) -> list[Span]:
    """controller.reconcile spans for RateLimitPolicy."""
    spans = []
    for trace in rl_traces:
        spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile"
                          and s.has_tag("event_kinds", "RateLimitPolicy.kuadrant.io")
            )
        )
    if len(spans) == 0:
        pytest.skip("No controller.reconcile spans with RateLimitPolicy.kuadrant.io in event_kinds")
    return spans


@pytest.fixture(scope="module")
def auth_reconciler_spans(auth_traces) -> dict[str, list[Span]]:
    """Auth reconciler operation spans with meaningful duration."""
    expected_ops = [
        "reconciler.auth_configs",
        "reconciler.istio_auth_cluster",
        "reconciler.authorino_istio_integration",
    ]
    operations_spans = {}
    for op_name in expected_ops:
        spans = []
        for trace in auth_traces:
            spans.extend(trace.filter_spans(
                lambda s, op=op_name: s.operation_name == op and s.duration > MIN_MEANINGFUL_DURATION_US
            ))
        operations_spans[op_name] = spans
    return operations_spans


@pytest.fixture(scope="module")
def rl_reconciler_spans(rl_traces) -> dict[str, list[Span]]:
    """RateLimitPolicy reconciler operation spans with meaningful duration."""
    expected_ops = [
        "reconciler.limitador_limits",
        "reconciler.istio_ratelimit_cluster",
        "workflow.limitador",
    ]
    operations_spans = {}
    for op_name in expected_ops:
        spans = []
        for trace in rl_traces:
            spans.extend(trace.filter_spans(
                lambda s, op=op_name: s.operation_name == op and s.duration > MIN_MEANINGFUL_DURATION_US
            ))
        operations_spans[op_name] = spans
    return operations_spans


@pytest.fixture(scope="module")
def auth_wasm_spans(auth_traces) -> list[Span]:
    """WASM-related spans from auth traces with meaningful duration."""
    spans = []
    for trace in auth_traces:
        spans.extend(trace.filter_spans(
            lambda s: ("wasm." in s.operation_name or "istio_extension" in s.operation_name)
                      and s.duration > MIN_MEANINGFUL_DURATION_US
        ))
    return spans


@pytest.fixture(scope="module")
def rl_wasm_spans(rl_traces) -> list[Span]:
    """WASM-related spans from rl traces with meaningful duration."""
    spans = []
    for trace in rl_traces:
        spans.extend(trace.filter_spans(
            lambda s: ("wasm." in s.operation_name or "istio_extension" in s.operation_name)
                      and s.duration > MIN_MEANINGFUL_DURATION_US
        ))
    return spans

