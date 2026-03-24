"""
Basic control plane reconciliation tracing tests.

Tests core policy reconciliation behavior including metadata, reconciliation spans,
child resource creation, duration metrics, and OTel semantic conventions.
"""

import pytest

from testsuite.tests.singlecluster.tracing.control_plane.conftest import MIN_MEANINGFUL_DURATION_US

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
    """
    reconcile_spans = request.getfixturevalue(reconcile_spans_fixture)
    reconcile_span = reconcile_spans[0]

    assert reconcile_span.has_tag("event_kinds")
    assert reconcile_span.has_tag("event_kinds", policy_kind)
    assert reconcile_span.has_tag("event_count") or reconcile_span.has_tag("events.count")
    if reconcile_span.has_tag("otel.status_code"):
        assert reconcile_span.get_tag("otel.status_code") != "ERROR"