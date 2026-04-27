"""
Policy lifecycle tracing tests.

Tests policy lifecycle events including validation, updates, deletion,
target changes, and multi-policy scenarios.
"""

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy
from testsuite.kubernetes import Selector

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def trace_snapshot_before_update(authorization, tracing):
    """Snapshot of trace and span IDs before policy update"""
    traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    trace_ids = {trace.trace_id for trace in traces}
    span_ids = {span.span_id for trace in traces for span in trace.spans}
    return {"trace_ids": trace_ids, "span_ids": span_ids}


@pytest.fixture(scope="module")
def updated_authorization(authorization, trace_snapshot_before_update):  # pylint: disable=unused-argument
    """
    Authorization policy after update.
    (trace_snapshot_before_update ensures snapshot taken before update)
    """
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.authorization.add_opa_policy("opa", "allow { false }", when=when_post)
    authorization.wait_for_ready()

    return authorization


def test_policy_update_generates_new_reconciliation_trace(updated_authorization, trace_snapshot_before_update, tracing):
    """
    Validate that policy updates generate new reconciliation traces
    """
    snapshot = trace_snapshot_before_update

    updated_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": updated_authorization.name()})

    # Find new reconcile spans (spans that weren't in the original snapshot)
    new_reconcile_spans = []
    for trace in updated_traces:
        for span in trace.filter_spans(lambda s: s.operation_name == "controller.reconcile"):
            if span.span_id not in snapshot["span_ids"]:
                new_reconcile_spans.append(span)

    assert len(new_reconcile_spans) > 0, "No new reconciliation traces found after policy update"

    # Find new policy spans (spans that weren't in the original snapshot)
    new_policy_spans = []
    for trace in updated_traces:
        for span in trace.filter_spans(lambda s: s.get_tag("policy.name") == updated_authorization.name()):
            if span.span_id not in snapshot["span_ids"]:
                new_policy_spans.append(span)

    assert len(new_policy_spans) > 0, "Updated reconciliation traces should reference the policy"


@pytest.fixture(scope="function")
def temp_deletion_policy(request, cluster, blame, route, module_label):
    """Temporary policy for deletion testing"""
    policy_type = getattr(request, "param", "auth")

    if policy_type == "auth":
        temp_policy = AuthPolicy.create_instance(cluster, blame("temp-authz"), route, labels={"testRun": module_label})
        temp_policy.identity.add_api_key("test_key", Selector(matchLabels={"app": module_label}))
    else:  # rate_limit
        temp_policy = RateLimitPolicy.create_instance(
            cluster, blame("temp-rlp"), route, labels={"testRun": module_label}
        )
        temp_policy.add_limit("basic", [Limit(5, "10s")])

    request.addfinalizer(temp_policy.delete)
    temp_policy.commit()
    temp_policy.wait_for_ready()
    return temp_policy


@pytest.mark.parametrize("temp_deletion_policy", ["auth", "rate_limit"], indirect=True)
@pytest.mark.flaky(reruns=0)
def test_policy_deletion_triggers_reconciliation_traces(temp_deletion_policy, tracing):
    """
    Validate that policy deletion triggers reconciliation traces.

    When a policy is deleted, the HTTPRoute/Gateway it was targeting gets reconciled
    to remove the policy's effects (not the deleted policy itself).
    """
    # Determine policy kind based on the policy type
    policy_kind = "AuthPolicy" if isinstance(temp_deletion_policy, AuthPolicy) else "RateLimitPolicy"

    # Snapshot existing spans before deletion
    all_traces_before = tracing.get_traces(service="kuadrant-operator")
    span_ids_before = {span.span_id for trace in all_traces_before for span in trace.spans}

    temp_deletion_policy.delete()
    temp_deletion_policy.wait_until(lambda obj: not obj.exists(), timelimit=30)

    all_traces = tracing.get_traces(service="kuadrant-operator")

    # Find new reconcile spans with policy deletion event
    deletion_traces = []
    for trace in all_traces:
        new_reconcile_spans = [
            s
            for s in trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile"
                and s.has_tag("event_kinds", f"{policy_kind}.kuadrant.io")
            )
            if s.span_id not in span_ids_before
        ]
        if new_reconcile_spans:
            deletion_traces.append(trace)

    assert len(deletion_traces) > 0, (
        f"No reconciliation traces found after deletion of policy {temp_deletion_policy.name()}. "
        "Expected HTTPRoute/Gateway reconciliation."
    )

    # Verify we see data_plane_policies workflow with non-trivial duration
    data_plane_workflow = []
    for trace in deletion_traces:
        data_plane_workflow.extend(
            trace.filter_spans(lambda s: s.operation_name == "workflow.data_plane_policies" and s.duration > 0)
        )

    assert (
        len(data_plane_workflow) > 0
    ), "Expected workflow.data_plane_policies spans with meaningful duration (>0μs) after policy deletion"

    # Verify we see effective_policies computation with non-trivial duration
    effective_policies_spans = []
    for trace in deletion_traces:
        effective_policies_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "effective_policies" and s.duration > 0)
        )

    assert (
        len(effective_policies_spans) > 0
    ), "Expected effective_policies computation with meaningful duration (>0μs) after policy deletion"


@pytest.fixture(scope="function")
def second_auth_policy(request, cluster, blame, route, module_label):
    """Second AuthPolicy targeting the same route for multi-policy testing"""
    second_policy = AuthPolicy.create_instance(cluster, blame("second-authz"), route, labels={"app": module_label})
    second_policy.identity.add_api_key("second_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy


def test_multiple_policies_same_target_traced_separately(authorization, second_auth_policy, auth_traces, tracing):
    """
    Validate traces when multiple policies target same HTTPRoute
    """
    second_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": second_auth_policy.name()})
    assert len(second_traces) > 0, f"No traces for second policy {second_auth_policy.name()}"

    first_uid_spans = []
    for trace in auth_traces:
        first_uid_spans.extend(
            trace.filter_spans(lambda s: s.has_tag("policy.name", authorization.name()) and s.has_tag("policy.uid"))
        )

    second_uid_spans = []
    for trace in second_traces:
        second_uid_spans.extend(
            trace.filter_spans(
                lambda s: s.has_tag("policy.name", second_auth_policy.name()) and s.has_tag("policy.uid")
            )
        )

    assert len(first_uid_spans) > 0, "Could not find policy.uid for first policy"
    assert len(second_uid_spans) > 0, "Could not find policy.uid for second policy"

    first_uid = first_uid_spans[0].get_tag("policy.uid")
    second_uid = second_uid_spans[0].get_tag("policy.uid")

    assert first_uid != second_uid, "Both policies should have distinct UIDs in traces"


@pytest.fixture(scope="function")
def second_route(request, cluster, blame, gateway, module_label, backend):
    """Second route for target change testing"""
    route = HTTPRoute.create_instance(cluster, blame("second-route"), gateway, {"app": module_label})
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="function")
def trace_snapshot_before_target_change(authorization, tracing):
    """Snapshot of trace and span IDs before policy target change"""
    traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    span_ids = {span.span_id for trace in traces for span in trace.spans}
    return span_ids


@pytest.fixture(scope="function")
def authorization_with_changed_target(
    authorization, second_route, trace_snapshot_before_target_change
):  # pylint: disable=unused-argument
    """
    Authorization policy with targetRef changed to second_route.
    (trace_snapshot_before_target_change ensures snapshot taken before change)
    """
    authorization.refresh()
    authorization.model.spec.targetRef = second_route.reference
    authorization.apply()
    authorization.wait_for_ready()
    return authorization


def test_policy_target_change_traced(authorization_with_changed_target, trace_snapshot_before_target_change, tracing):
    """Validate traces when policy's targetRef changes"""
    snapshot = trace_snapshot_before_target_change

    updated_traces = tracing.get_traces(
        service="kuadrant-operator", tags={"policy.name": authorization_with_changed_target.name()}
    )

    # Find new reconcile spans (spans that weren't in the original snapshot)
    new_reconcile_spans = []
    for trace in updated_traces:
        for span in trace.filter_spans(lambda s: s.operation_name == "controller.reconcile"):
            if span.span_id not in snapshot:
                new_reconcile_spans.append(span)

    assert len(new_reconcile_spans) > 0, "No new reconciliation spans found after target change"
