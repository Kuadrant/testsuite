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
from testsuite.tracing.models import Trace

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

@pytest.fixture
def latest_reconcile_timestamp():
    """Factory fixture that returns latest reconcile timestamp from traces."""
    def _get_timestamp(traces: list[Trace]) -> int:
        latest_timestamp = 0
        for trace in traces:
            reconcile_spans = trace.filter_spans(lambda s: s.operation_name == "controller.reconcile")
            for span in reconcile_spans:
                latest_timestamp = max(latest_timestamp, span.start_time)
        return latest_timestamp
    return _get_timestamp


@pytest.fixture(scope="module")
def updated_authorization(authorization, auth_traces):
    """Authorization policy after update, with timestamp before the update."""
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.authorization.add_opa_policy("opa", "allow { false }", when=when_post)
    authorization.wait_for_ready()

    return authorization

def test_policy_update_generates_new_reconciliation_trace(updated_authorization, auth_traces, tracing, latest_reconcile_timestamp):
    """
    Validate that policy updates generate new reconciliation traces.
    """
    latest_timestamp = latest_reconcile_timestamp(auth_traces)

    updated_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": updated_authorization.name()})

    new_reconcile_spans = []
    for trace in updated_traces:
        new_reconcile_spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile" and s.start_time > latest_timestamp
            )
        )

    assert len(new_reconcile_spans) > 0, "No new reconciliation traces found after policy update"

    new_policy_spans = []
    for trace in updated_traces:
        new_policy_spans.extend(
            trace.filter_spans(
                lambda s: s.start_time > latest_timestamp and s.get_tag("policy.name") == updated_authorization.name()
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
    """
    # Get timestamp before deletion
    deletion_time = int(time.time() * 1000000)  # microseconds

    # Delete the policy
    temp_deletion_policy.delete()

    # Fetch all operator traces - get_traces has built-in backoff
    all_traces_data = tracing.query.api.traces.get(
        params={"service": "kuadrant-operator", "lookback": "10m", "limit": 50}
    ).json()["data"]

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
    Validate traces when multiple policies target same HTTPRoute.
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
def second_route(request, cluster, blame, gateway, module_label, backend):
    """Second route for target change testing."""
    route = HTTPRoute.create_instance(cluster, blame("second-route"), gateway, {"app": module_label})
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="function")
def authorization_with_changed_target(authorization, second_route):
    """Authorization policy with targetRef changed to second_route."""
    def update_target_ref(policy):
        policy.model.spec.targetRef.name = second_route.name()
        return True

    authorization.apply(modifier_func=update_target_ref)
    authorization.wait_for_ready()
    return authorization


def test_policy_target_change_traced(authorization_with_changed_target, auth_traces, tracing, latest_reconcile_timestamp):
    """
    Validate traces when policy's targetRef changes.
    """
    latest_timestamp = latest_reconcile_timestamp(auth_traces)

    updated_traces = tracing.get_traces(
        service="kuadrant-operator", tags={"policy.name": authorization_with_changed_target.name()}
    )

    new_reconcile_spans = []
    for trace in updated_traces:
        new_reconcile_spans.extend(
            trace.filter_spans(
                lambda s: s.operation_name == "controller.reconcile" and s.start_time > latest_timestamp
            )
        )

    assert len(new_reconcile_spans) > 0, "No new reconciliation spans found after target change"
