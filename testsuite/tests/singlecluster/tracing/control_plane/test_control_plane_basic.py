"""
Basic control plane reconciliation tracing tests.

Tests core policy reconciliation behavior including metadata, reconciliation spans,
child resource creation, duration metrics, and OTel semantic conventions.
"""

import pytest

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.mark.parametrize(
    "policy_spans_fixture,policy_fixture,policy_kind",
    [
        ("auth_policy_spans", "authorization", "AuthPolicy"),
        ("rl_policy_spans", "rate_limit", "RateLimitPolicy"),
    ],
)
def test_operator_traces_include_policy_context(policy_spans_fixture, policy_fixture, policy_kind, request):
    """
    Validate that operator traces include policy metadata.

    Verifies:
    - Policy-specific spans include policy.name, policy.namespace, policy.kind, policy.uid
    """
    policy_spans = request.getfixturevalue(policy_spans_fixture)
    policy = request.getfixturevalue(policy_fixture)

    span = policy_spans[0]
    assert span.get_tag("policy.name") == policy.name()
    assert span.get_tag("policy.namespace") == policy.namespace()
    assert span.get_tag("policy.kind") == policy_kind
    assert span.has_tag("policy.uid")


@pytest.mark.parametrize(
    "reconcile_spans_fixture,policy_kind",
    [
        ("auth_reconcile_spans", "AuthPolicy.kuadrant.io"),
        ("rl_reconcile_spans", "RateLimitPolicy.kuadrant.io"),
    ],
)
def test_controller_reconcile_spans_include_event_details(reconcile_spans_fixture, policy_kind, request):
    """
    Validate that controller.reconcile spans include event_kinds and reconciliation details.

    Verifies:
    - controller.reconcile spans include event_kinds tag with policy types
    - Reconcile spans include event_count
    - Spans have successful status (no ERROR)
    """
    reconcile_spans = request.getfixturevalue(reconcile_spans_fixture)
    reconcile_span = reconcile_spans[0]

    assert reconcile_span.has_tag("event_kinds")
    assert reconcile_span.has_tag("event_kinds", policy_kind)
    assert reconcile_span.has_tag("event_count") or reconcile_span.has_tag("events.count")
    if reconcile_span.has_tag("otel.status_code"):
        assert reconcile_span.get_tag("otel.status_code") != "ERROR"


@pytest.mark.parametrize(
    "reconciler_spans_fixture,wasm_spans_fixture,policy_kind",
    [
        ("auth_reconciler_spans", "auth_wasm_spans", "AuthPolicy"),
        ("rl_reconciler_spans", "rl_wasm_spans", "RateLimitPolicy"),
    ],
)
def test_operator_traces_show_child_resource_creation(
    reconciler_spans_fixture, wasm_spans_fixture, policy_kind, request
):
    """
    Validate that operator traces show child resource creation.

    Verifies that reconciliation traces include spans for sub-operations like:
    - Creating AuthConfig resources (for AuthPolicy)
    - Creating Limitador limits (for RateLimitPolicy)
    - Updating WASM plugin configuration
    - Updating Istio resources (EnvoyFilter, etc.)
    """
    reconciler_spans = request.getfixturevalue(reconciler_spans_fixture)
    wasm_spans = request.getfixturevalue(wasm_spans_fixture)
    min_duration_us = 50

    # Verify expected reconciler operations are present with meaningful work
    for op_name, spans in reconciler_spans.items():
        assert len(spans) > 0, (
            f"No {op_name} span with duration > {min_duration_us}us found for {policy_kind}. "
            f"This indicates the operation didn't perform actual work."
        )

    # Verify WASM plugin configuration is built (common to both policies)
    assert len(wasm_spans) > 0, f"No WASM-related spans with duration > {min_duration_us}us found for {policy_kind}"