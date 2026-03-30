"""
Basic control plane reconciliation tracing tests.
"""

import pytest

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def policy_lifecycle_trace(request, tracing, skip_or_fail):
    """Find trace containing complete policy lifecycle (validation + status update)"""
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": policy.name()})

    # Find trace with both validation and status update spans for this policy
    found_trace = None
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
                found_trace = trace
                break

    if found_trace is None:
        skip_or_fail(f"Traces for reconciling policy {policy.name()} were not found")

    return found_trace


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_lifecycle_has_consistent_metadata(request, policy_lifecycle_trace):
    """Validate policy metadata is consistent across validation and status update phases"""
    # Get policy info from parameterization
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    # Extract validation and status spans directly
    validate_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}.validate" and s.get_tag("policy.name") == policy.name()
    )[0]

    status_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}"
        and s.get_tag("policy.name") == policy.name()
        and s.has_log_field("event", "policy status updated successfully")
    )[0]

    # Validate span metadata
    assert validate_span.get_tag("policy.uid") == status_span.get_tag("policy.uid")
    assert validate_span.get_tag("policy.name") == policy.name()
    assert validate_span.get_tag("policy.namespace") == policy.namespace()
    assert validate_span.get_tag("policy.kind") == policy_kind

    # Status span metadata (should match validation)
    assert status_span.get_tag("policy.name") == policy.name()
    assert status_span.get_tag("policy.namespace") == policy.namespace()
    assert status_span.get_tag("policy.kind") == policy_kind


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_validation_before_status_update(request, policy_lifecycle_trace):
    """Validate policy validation happens before status update in the trace"""
    # Get policy info from parameterization
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    # Extract spans directly
    validate_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}.validate" and s.get_tag("policy.name") == policy.name()
    )[0]

    status_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}"
        and s.get_tag("policy.name") == policy.name()
        and s.has_log_field("event", "policy status updated successfully")
    )[0]

    assert validate_span.start_time < status_span.start_time, "Validation should happen before status update"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_spans_have_correct_log_messages(request, policy_lifecycle_trace):
    """Validate policy spans have expected log messages"""
    # Get policy info from parameterization
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    # Extract spans directly
    validate_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}.validate" and s.get_tag("policy.name") == policy.name()
    )[0]

    status_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}"
        and s.get_tag("policy.name") == policy.name()
        and s.has_log_field("event", "policy status updated successfully")
    )[0]

    assert validate_span.has_log_field("event", "policy validated successfully")
    assert status_span.has_log_field("event", "policy status updated successfully")


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_policy_spans_are_in_workflow_hierarchy(request, policy_lifecycle_trace):
    """Validate policy spans are part of workflow.data_plane_policies hierarchy"""
    # Get policy info from parameterization
    policy_fixture_name = getattr(request, "param", "authorization")
    policy = request.getfixturevalue(policy_fixture_name)
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    # Extract spans directly
    validate_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}.validate" and s.get_tag("policy.name") == policy.name()
    )[0]

    status_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == f"policy.{policy_kind}"
        and s.get_tag("policy.name") == policy.name()
        and s.has_log_field("event", "policy status updated successfully")
    )[0]

    # Validation span hierarchy
    validation_parent = policy_lifecycle_trace.get_span_by_id(validate_span.get_parent_id())
    assert validation_parent is not None
    assert validation_parent.operation_name.startswith("validator.")

    validation_grandparent = policy_lifecycle_trace.get_span_by_id(validation_parent.get_parent_id())
    assert validation_grandparent is not None
    assert validation_grandparent.operation_name == "validation"

    validation_great_grandparent = policy_lifecycle_trace.get_span_by_id(validation_grandparent.get_parent_id())
    assert validation_great_grandparent is not None
    assert validation_great_grandparent.operation_name == "workflow.data_plane_policies"

    # Status span hierarchy
    status_parent = policy_lifecycle_trace.get_span_by_id(status_span.get_parent_id())
    assert status_parent is not None
    assert status_parent.operation_name.startswith("status.")

    status_grandparent = policy_lifecycle_trace.get_span_by_id(status_parent.get_parent_id())
    assert status_grandparent is not None
    assert status_grandparent.operation_name == "status_update"

    status_great_grandparent = policy_lifecycle_trace.get_span_by_id(status_grandparent.get_parent_id())
    assert status_great_grandparent is not None
    assert status_great_grandparent.operation_name == "workflow.data_plane_policies"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_controller_reconcile_includes_event_details(request, policy_lifecycle_trace):
    """Validate controller.reconcile span has event details"""
    # Get policy info from parameterization
    policy_fixture_name = getattr(request, "param", "authorization")
    policy_kind = "AuthPolicy" if "auth" in policy_fixture_name else "RateLimitPolicy"

    # Extract reconcile span directly
    reconcile_span = policy_lifecycle_trace.filter_spans(
        lambda s: s.operation_name == "controller.reconcile" and s.has_tag("event_kinds", f"{policy_kind}.kuadrant.io")
    )[0]

    assert reconcile_span.has_tag("event_kinds")

    event_kinds = str(reconcile_span.get_tag("event_kinds"))
    assert f"{policy_kind}.kuadrant.io" in event_kinds, f"event_kinds should contain {policy_kind}.kuadrant.io"

    assert reconcile_span.has_tag("event_count") or reconcile_span.has_tag("events.count")


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
def test_policy_specific_reconcilers_executed(policy_lifecycle_trace, expected_reconcilers):
    """Validate policy-specific reconcilers are executed"""
    # Find effective_policies span
    effective_policies_span = policy_lifecycle_trace.filter_spans(lambda s: s.operation_name == "effective_policies")[0]

    # Get all reconciler children
    reconciler_spans = {}
    for span in policy_lifecycle_trace.get_children(effective_policies_span.span_id):
        if span.operation_name.startswith("reconciler."):
            reconciler_spans[span.operation_name] = span

    # Verify expected reconcilers exist and succeeded
    for expected_reconciler in expected_reconcilers:
        assert expected_reconciler in reconciler_spans, f"Should have {expected_reconciler} reconciler span"

        span = reconciler_spans[expected_reconciler]
        assert span.get_tag("otel.status_code") == "OK"


@pytest.mark.parametrize("policy_lifecycle_trace", ["authorization", "rate_limit"], indirect=True)
def test_effective_policies_computed_before_reconcilers(policy_lifecycle_trace):
    """Validate effective policies are computed before reconcilers run."""
    # Find effective_policies span
    effective_policies_span = policy_lifecycle_trace.filter_spans(lambda s: s.operation_name == "effective_policies")[0]

    # Find effective_policies.compute child
    compute_spans = [
        s
        for s in policy_lifecycle_trace.get_children(effective_policies_span.span_id)
        if s.operation_name == "effective_policies.compute"
    ]
    assert len(compute_spans) > 0, "Should have effective_policies.compute span"
    compute_span = compute_spans[0]

    # Get all reconciler children
    reconciler_spans = [
        span
        for span in policy_lifecycle_trace.get_children(effective_policies_span.span_id)
        if span.operation_name.startswith("reconciler.")
    ]

    # All reconcilers should start after compute finishes
    for reconciler_span in reconciler_spans:
        assert (
            compute_span.start_time + compute_span.duration <= reconciler_span.start_time
        ), f"{reconciler_span.operation_name} should start after effective_policies.compute finishes"
