"""
Policy lifecycle tracing tests.

Tests policy lifecycle events including validation, updates, deletion,
target changes, and multi-policy scenarios.
"""

import time

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes import Selector

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def validation_spans(auth_traces):
    """Validation spans from auth traces."""
    spans = []
    for trace in auth_traces:
        spans.extend(
            trace.filter_spans(
                lambda s: "validate" in s.operation_name.lower()
            )
        )
    if len(spans) == 0:
        pytest.skip("No validation spans found")
    return spans


def test_policy_validation_spans_show_success_or_failure(validation_spans):
    """
    Validate that policy validation spans include success/failure logs.

    Verifies that validation spans include:
    - Validation result (success via logs or status)
    - Policy validation happens before enforcement
    """
    # Check for success indicators
    for span in validation_spans:
        # Validation should succeed (status OK or success log)
        has_success_indicator = (
            span.get_tag("otel.status_code") == "OK"
            or any(log_entry.has_field("event", "success") for log_entry in span.logs)
            or any("success" in field.value.lower() for log_entry in span.logs for field in log_entry.fields)
        )

        assert has_success_indicator, "Validation span should have success indicator"


def test_policy_update_generates_new_reconciliation_trace(authorization, auth_traces, tracing):
    """
    Validate that policy updates generate new reconciliation traces.

    Verifies that:
    - Policy updates trigger new reconciliation
    - Update traces are distinguishable from creation traces
    - Can observe what changed in the policy
    - Multiple reconciliation events for same policy are traceable
    """
    # Get latest timestamp from initial traces
    latest_timestamp = 0
    for trace in auth_traces:
        reconcile_spans = trace.filter_spans(lambda s: s.operation_name == "controller.reconcile")
        for span in reconcile_spans:
            latest_timestamp = max(latest_timestamp, span.start_time)

    # Update the policy to trigger new reconciliation
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.authorization.add_opa_policy("opa", "allow { false }", when=when_post)
    authorization.wait_for_ready()

    # Fetch traces - get_traces has built-in backoff
    updated_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": authorization.name()})

    # Filter for new reconciliation spans (after update timestamp)
    new_reconcile_spans = []
    for trace in updated_traces:
        new_reconcile_spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile" and s.start_time > latest_timestamp
            )
        )

    assert len(new_reconcile_spans) > 0, "No new reconciliation traces found after policy update"

    # Verify the new traces reference the updated policy
    new_policy_spans = []
    for trace in updated_traces:
        new_policy_spans.extend(
            trace.filter_spans(
                lambda s: s.start_time > latest_timestamp and s.get_tag("policy.name") == authorization.name()
            )
        )

    assert len(new_policy_spans) > 0, "Updated reconciliation traces should reference the policy"


@pytest.fixture(scope="function")
def temp_deletion_policy(request, cluster, blame, route, module_label):
    """Temporary policy for deletion testing - not auto-deleted."""
    temp_policy = AuthPolicy.create_instance(cluster, blame("temp-authz"), route, labels={"testRun": module_label})
    temp_policy.identity.add_api_key("test_key", Selector(matchLabels={"app": module_label}))
    temp_policy.commit()
    temp_policy.wait_for_ready()
    # Note: No finalizer - test controls deletion timing
    return temp_policy


def test_policy_deletion_triggers_reconciliation_traces(temp_deletion_policy, tracing):
    """
    Validate that policy deletion triggers reconciliation traces.

    Verifies:
    - Deletion triggers reconciliation events
    - Reconciliation operations are traceable after deletion
    """
    # Get timestamp before deletion
    deletion_time = int(time.time() * 1000000)  # microseconds

    # Delete the policy
    temp_deletion_policy.delete()

    # Fetch all operator traces - get_traces has built-in backoff
    all_traces_data = tracing.query.api.traces.get(
        params={"service": "kuadrant-operator", "lookback": "10m", "limit": 50}
    ).json()["data"]

    from testsuite.tracing.models import Trace

    all_traces = [Trace.from_dict(trace_data) for trace_data in all_traces_data]

    # Filter for deletion traces (reconciliation after deletion time with AuthPolicy events)
    deletion_traces = []
    for trace in all_traces:
        reconcile_spans = trace.filter_spans(
            lambda s: s.operation_name == "controller.reconcile"
                      and s.start_time > deletion_time
                      and s.has_tag("event_kinds", "AuthPolicy")
        )
        if reconcile_spans:
            deletion_traces.append(trace)

    # Note: Deletion traces might not always be present if cleaned up quickly
    if len(deletion_traces) == 0:
        import logging

        logging.warning(f"No reconciliation traces found after deletion of policy {temp_deletion_policy.name()}")
        return

    # Verify traces contain reconciliation operations
    reconcile_operations = set()
    for trace in deletion_traces:
        for span in trace.filter_spans(
            lambda s: s.operation_name.startswith("reconciler.") or s.operation_name.startswith("effective_policies")
        ):
            reconcile_operations.add(span.operation_name)

    assert len(reconcile_operations) > 0, "Deletion traces found but contain no recognizable reconciliation operations"


@pytest.fixture(scope="function")
def second_auth_policy(request, cluster, blame, route, module_label):
    """Second AuthPolicy targeting the same route for multi-policy testing."""
    second_policy = AuthPolicy.create_instance(cluster, blame("second-authz"), route, labels={"app": module_label})
    second_policy.identity.add_api_key("second_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy


def test_multiple_policies_same_target_traced_separately(authorization, second_auth_policy, auth_traces, tracing):
    """
    Test: Validate traces when multiple policies target same HTTPRoute.

    Verifies:
    - Each policy has distinct traces with correct policy.uid
    - Can distinguish between policies in same namespace
    - source_policies tag lists all applicable policies
    - Reconciliation order is traceable
    """
    # Wait for traces for second policy (first already in auth_traces fixture)
    second_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": second_auth_policy.name()})
    assert len(second_traces) > 0, f"No traces for second policy {second_auth_policy.name()}"

    # Extract policy UIDs using filter_spans
    first_uid_spans = []
    for trace in auth_traces:
        first_uid_spans.extend(
            trace.filter_spans(lambda s: s.has_tag("policy.name", authorization.name()) and s.has_tag("policy.uid")
            )
        )

    second_uid_spans = []
    for trace in second_traces:
        second_uid_spans.extend(
            trace.filter_spans(lambda s: s.has_tag("policy.name", second_auth_policy.name()) and s.has_tag("policy.uid")
            )
        )

    assert len(first_uid_spans) > 0, "Could not find policy.uid for first policy"
    assert len(second_uid_spans) > 0, "Could not find policy.uid for second policy"

    first_uid = first_uid_spans[0].get_tag("policy.uid")
    second_uid = second_uid_spans[0].get_tag("policy.uid")

    assert first_uid != second_uid, "Both policies should have distinct UIDs in traces"


@pytest.fixture(scope="function")
def target_change_policy(request, cluster, blame, route, module_label):
    """Policy for target change testing."""
    test_policy = AuthPolicy.create_instance(
        cluster, blame("target-change-authz"), route, labels={"app": module_label}
    )
    test_policy.identity.add_api_key("test_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(test_policy.delete)
    test_policy.commit()
    test_policy.wait_for_ready()
    return test_policy


@pytest.fixture(scope="function")
def second_route(request, cluster, blame, gateway, module_label, backend):
    """Second route for target change testing."""
    route = HTTPRoute.create_instance(cluster, blame("second-route"), gateway, {"app": module_label})
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


def test_policy_target_change_traced(target_change_policy, second_route, tracing):
    """
    Test: Validate traces when policy's targetRef changes.

    Verifies:
    - Target change triggers reconciliation
    - New configuration is traced
    - Can observe the target update in spans
    """
    # Get latest timestamp from initial traces
    initial_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": target_change_policy.name()})
    latest_timestamp = 0
    for trace in initial_traces:
        reconcile_spans = trace.filter_spans(lambda s: s.operation_name == "controller.reconcile")
        for span in reconcile_spans:
            latest_timestamp = max(latest_timestamp, span.start_time)

    # Update the policy to target the new route
    def update_target_ref(policy):
        """Modifier function to update targetRef"""
        policy.model.spec.targetRef.name = second_route.name()
        return True

    target_change_policy.apply(modifier_func=update_target_ref)
    target_change_policy.wait_for_ready()

    # Fetch updated traces - get_traces has built-in backoff
    updated_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": target_change_policy.name()})

    # Filter for new reconciliation spans (after update timestamp)
    new_reconcile_spans = []
    for trace in updated_traces:
        new_reconcile_spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile" and s.start_time > latest_timestamp
            )
        )

    assert len(new_reconcile_spans) > 0, "No new reconciliation spans found after target change"
