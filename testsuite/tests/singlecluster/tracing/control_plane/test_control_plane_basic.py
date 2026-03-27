"""
Basic control plane reconciliation tracing tests.
"""

import pytest

from testsuite.tests.conftest import skip_or_fail

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def policy_lifecycle_trace(request, tracing, skip_or_fail):
    """Find trace containing complete policy lifecycle (validation + status update)"""
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    traces = tracing.get_traces(service="kuadrant-operator")

    # Find trace with both validation and status update spans for this policy
    for trace in traces:
        reconcile_spans = trace.filter_spans(
            lambda s: s.operation_name == "controller.reconcile"
            and s.has_tag("event_kinds", f"{policy_kind}.kuadrant.io")
        )

        if reconcile_spans:
            validate_spans = trace.filter_spans(
                lambda s: s.operation_name == f"policy.{policy_kind}.validate"
                and s.get_tag("policy.name") == policy.name()
            )
            status_spans = trace.filter_spans(
                lambda s: s.operation_name == f"policy.{policy_kind}"
                and s.get_tag("policy.name") == policy.name()
                and s.has_log_field("event", "policy status updated successfully")
            )

            if validate_spans and status_spans:
                return {
                    "trace": trace,
                    "policy": policy,
                    "policy_kind": policy_kind,
                    "validate_span": validate_spans[0],
                    "status_span": status_spans[0],
                    "reconcile_span": reconcile_spans[0],
                }

    skip_or_fail(f"Traces for reconciling policy {policy.name()} were not found")


@pytest.fixture(scope="module")
def policy_validate_span(policy_lifecycle_trace):
    """Policy validation span from the lifecycle trace"""
    return policy_lifecycle_trace["validate_span"]


@pytest.fixture(scope="module")
def policy_status_span(policy_lifecycle_trace):
    """Policy status update span from the lifecycle trace"""
    return policy_lifecycle_trace["status_span"]


@pytest.fixture(scope="module")
def controller_reconcile_span(policy_lifecycle_trace):
    """Controller reconcile root span from the lifecycle trace"""
    return policy_lifecycle_trace["reconcile_span"]


@pytest.fixture(scope="module")
def effective_policies_span(skip_or_fail, policy_lifecycle_trace):
    """Effective policies computation span"""
    trace = policy_lifecycle_trace["trace"]

    spans = trace.filter_spans(lambda s: s.operation_name == "effective_policies")
    if not spans:
        skip_or_fail("Control plane tracing not enabled (no OTEL_* env vars on kuadrant-operator)")

    return spans[0]


@pytest.fixture(scope="module")
def reconciler_spans(policy_lifecycle_trace, effective_policies_span):
    """Dict of reconciler spans (by operation name)"""
    trace = policy_lifecycle_trace["trace"]

    # Get all reconciler children
    reconcilers = {}
    for span in trace.get_children(effective_policies_span.span_id):
        if span.operation_name.startswith("reconciler."):
            reconcilers[span.operation_name] = span

    return reconcilers


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_lifecycle_has_consistent_metadata(policy_lifecycle_trace, policy_validate_span, policy_status_span):
    """Validate policy metadata is consistent across validation and status update phases"""
    policy = policy_lifecycle_trace["policy"]
    policy_kind = policy_lifecycle_trace["policy_kind"]

    # Same policy metadata in both phases
    assert policy_validate_span.get_tag("policy.uid") == policy_status_span.get_tag("policy.uid")
    assert policy_validate_span.get_tag("policy.name") == policy.name()
    assert policy_status_span.get_tag("policy.name") == policy.name()
    assert policy_validate_span.get_tag("policy.namespace") == policy.namespace()
    assert policy_status_span.get_tag("policy.namespace") == policy.namespace()
    assert policy_validate_span.get_tag("policy.kind") == policy_kind
    assert policy_status_span.get_tag("policy.kind") == policy_kind


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_validation_before_status_update(policy_validate_span, policy_status_span):
    """Validate policy validation happens before status update in the trace"""
    assert (
        policy_validate_span.start_time < policy_status_span.start_time
    ), "Validation should happen before status update"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_spans_have_correct_log_messages(policy_validate_span, policy_status_span):
    """Validate policy spans have expected log messages"""
    assert policy_validate_span.has_log_field("event", "policy validated successfully")
    assert policy_status_span.has_log_field("event", "policy status updated successfully")


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_spans_are_in_workflow_hierarchy(policy_lifecycle_trace, policy_validate_span, policy_status_span):
    """Validate policy spans are part of workflow.data_plane_policies hierarchy"""
    trace = policy_lifecycle_trace["trace"]

    # Validation span hierarchy
    validation_parent = trace.get_span_by_id(policy_validate_span.get_parent_id())
    assert validation_parent is not None
    assert validation_parent.operation_name.startswith("validator.")

    validation_grandparent = trace.get_span_by_id(validation_parent.get_parent_id())
    assert validation_grandparent is not None
    assert validation_grandparent.operation_name == "validation"

    validation_great_grandparent = trace.get_span_by_id(validation_grandparent.get_parent_id())
    assert validation_great_grandparent is not None
    assert validation_great_grandparent.operation_name == "workflow.data_plane_policies"

    # Status span hierarchy
    status_parent = trace.get_span_by_id(policy_status_span.get_parent_id())
    assert status_parent is not None
    assert status_parent.operation_name.startswith("status.")

    status_grandparent = trace.get_span_by_id(status_parent.get_parent_id())
    assert status_grandparent is not None
    assert status_grandparent.operation_name == "status_update"

    status_great_grandparent = trace.get_span_by_id(status_grandparent.get_parent_id())
    assert status_great_grandparent is not None
    assert status_great_grandparent.operation_name == "workflow.data_plane_policies"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_controller_reconcile_includes_event_details(policy_lifecycle_trace, controller_reconcile_span):
    """Validate controller.reconcile span has event details"""
    policy_kind = policy_lifecycle_trace["policy_kind"]

    assert controller_reconcile_span.has_tag("event_kinds")

    event_kinds = str(controller_reconcile_span.get_tag("event_kinds"))
    assert f"{policy_kind}.kuadrant.io" in event_kinds, f"event_kinds should contain {policy_kind}.kuadrant.io"

    assert controller_reconcile_span.has_tag("event_count") or controller_reconcile_span.has_tag("events.count")


@pytest.mark.parametrize(
    "policy_lifecycle_trace,expected_reconcilers",
    [
        (
            "authorization",
            ["reconciler.auth_configs", "reconciler.istio_auth_cluster", "reconciler.authorino_istio_integration"],
        ),
        ("rate_limit", ["reconciler.limitador_limits", "reconciler.istio_ratelimit_cluster"]),
    ],
    indirect=["policy_lifecycle_trace"],
)
def test_policy_specific_reconcilers_executed(reconciler_spans, expected_reconcilers):
    """Validate policy-specific reconcilers are executed"""
    for expected_reconciler in expected_reconcilers:
        assert expected_reconciler in reconciler_spans, f"Should have {expected_reconciler} reconciler span"

        span = reconciler_spans[expected_reconciler]
        assert span.get_tag("otel.status_code") == "OK"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_effective_policies_computed_before_reconcilers(
    policy_lifecycle_trace, effective_policies_span, reconciler_spans
):
    """Validate effective policies are computed before reconcilers run."""
    trace = policy_lifecycle_trace["trace"]

    # Find effective_policies.compute child
    compute_spans = [
        s
        for s in trace.get_children(effective_policies_span.span_id)
        if s.operation_name == "effective_policies.compute"
    ]
    assert len(compute_spans) > 0, "Should have effective_policies.compute span"
    compute_span = compute_spans[0]

    # All reconcilers should start after compute finishes
    for reconciler_span in reconciler_spans.values():
        assert (
            compute_span.start_time + compute_span.duration <= reconciler_span.start_time
        ), f"{reconciler_span.operation_name} should start after effective_policies.compute finishes"
