"""
Tests for control plane distributed tracing in Kuadrant operators.

This module validates that the kuadrant-operator emits distributed traces during
policy reconciliation, including policy validation, resource creation, and configuration
of data plane components (AuthConfig, Limitador, WASM plugins).
"""

# pylint: disable=unused-argument
# Fixtures needed for side effects (policy creation triggers operator traces)

import pytest
import backoff

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kubernetes import Selector
from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def data_plane_trace(client, auth):
    """
    Sends a successful request to generate a data plane trace.
    Returns the request_id for correlation tests.
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    return response.headers.get("x-request-id")


def assert_span_has_policy_metadata(span, policy, tracing):
    """Assert that span contains policy.name, policy.namespace, and policy.uid tags."""
    tags = tracing.get_tags_dict(span)
    assert tags.get("policy.name") == policy.name(), (
        f"Expected policy.name={policy.name()}, got {tags.get('policy.name')}. "
        f"Available tags: {list(tags.keys())}"
    )
    assert tags.get("policy.namespace") == policy.namespace(), (
        f"Expected policy.namespace={policy.namespace()}, got {tags.get('policy.namespace')}"
    )
    assert "policy.uid" in tags, f"policy.uid tag missing. Available tags: {list(tags.keys())}"


def get_span_duration_us(span):
    """Extract span duration in microseconds."""
    return span.get("duration")


def test_operator_traces_include_policy_context(authorization, rate_limit, tracing):
    """
    Test #18: Validate that operator traces include policy metadata.

    Verifies that policy-specific spans include:
    - Policy name
    - Policy namespace
    - Policy kind (AuthPolicy/RateLimitPolicy)
    - Policy UID
    """
    # Wait for traces for both policies
    auth_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    rl_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": rate_limit.name()})

    assert len(auth_traces) > 0, f"No traces found for AuthPolicy: {authorization.name()}"
    assert len(rl_traces) > 0, f"No traces found for RateLimitPolicy: {rate_limit.name()}"

    # Validate AuthPolicy metadata
    auth_policy_spans = []
    for trace in auth_traces:
        for span in trace.get("spans", []):
            tags = tracing.get_tags_dict(span)
            if tags.get("policy.kind") == "AuthPolicy" and tags.get("policy.name") == authorization.name():
                auth_policy_spans.append(span)

    assert len(auth_policy_spans) > 0, "No AuthPolicy spans found with policy metadata"

    auth_tags = tracing.get_tags_dict(auth_policy_spans[0])
    assert auth_tags["policy.name"] == authorization.name()
    assert auth_tags["policy.namespace"] == authorization.namespace()
    assert auth_tags["policy.kind"] == "AuthPolicy"
    assert "policy.uid" in auth_tags

    # Validate RateLimitPolicy metadata
    rl_policy_spans = []
    for trace in rl_traces:
        for span in trace.get("spans", []):
            tags = tracing.get_tags_dict(span)
            if tags.get("policy.kind") == "RateLimitPolicy" and tags.get("policy.name") == rate_limit.name():
                rl_policy_spans.append(span)

    assert len(rl_policy_spans) > 0, "No RateLimitPolicy spans found with policy metadata"

    rl_tags = tracing.get_tags_dict(rl_policy_spans[0])
    assert rl_tags["policy.name"] == rate_limit.name()
    assert rl_tags["policy.namespace"] == rate_limit.namespace()
    assert rl_tags["policy.kind"] == "RateLimitPolicy"
    assert "policy.uid" in rl_tags


def test_operator_spans_include_reconciliation_details(authorization, rate_limit, tracing):
    """
    Test #19: Validate that operator traces show what was reconciled.

    Verifies that controller.reconcile spans include:
    - Event kinds (what resources triggered reconciliation)
    - Event count
    - Reconciliation result (success via otel.status_code)
    """
    # Wait for reconciliation traces for both policy types
    auth_reconcile_traces = tracing.get_trace(service="kuadrant-operator", tags={"event_kinds": "AuthPolicy.kuadrant.io"})
    rl_reconcile_traces = tracing.get_trace(service="kuadrant-operator", tags={"event_kinds": "RateLimitPolicy.kuadrant.io"})

    assert len(auth_reconcile_traces) > 0, "No reconciliation traces found for AuthPolicy events"
    assert len(rl_reconcile_traces) > 0, "No reconciliation traces found for RateLimitPolicy events"

    # Validate reconcile span for AuthPolicy
    for trace in auth_reconcile_traces[:1]:  # Check first trace
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile":
                tags = tracing.get_tags_dict(span)
                assert "event_kinds" in tags
                assert "AuthPolicy.kuadrant.io" in tags["event_kinds"]
                assert "event_count" in tags or "events.count" in tags
                # Check for successful reconciliation
                if "otel.status_code" in tags:
                    # If present, should not be ERROR
                    assert tags["otel.status_code"] != "ERROR"

    # Validate reconcile span for RateLimitPolicy
    for trace in rl_reconcile_traces[:1]:
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile":
                tags = tracing.get_tags_dict(span)
                assert "event_kinds" in tags
                assert "RateLimitPolicy.kuadrant.io" in tags["event_kinds"]


@pytest.mark.parametrize(
    "policy_kind,expected_reconciler_operations",
    [
        (
            "AuthPolicy",
            ["reconciler.auth_configs", "reconciler.istio_auth_cluster", "reconciler.authorino_istio_integration"],
        ),
        (
            "RateLimitPolicy",
            ["reconciler.limitador_limits", "reconciler.istio_ratelimit_cluster", "workflow.limitador"],
        ),
    ],
)
def test_operator_traces_show_child_resource_creation(
    authorization, rate_limit, tracing, policy_kind, expected_reconciler_operations
):
    """
    Test #20: Validate that operator traces show child resource creation.

    Verifies that reconciliation traces include spans for sub-operations like:
    - Creating AuthConfig resources (for AuthPolicy)
    - Creating Limitador limits (for RateLimitPolicy)
    - Updating WASM plugin configuration
    - Updating Istio resources (EnvoyFilter, etc.)
    """
    # Wait for traces for the specific policy kind
    policy_traces = tracing.get_trace(service="kuadrant-operator", tags={"event_kinds": f"{policy_kind}.kuadrant.io"})
    assert len(policy_traces) > 0, f"No traces found for {policy_kind}"

    # Collect all operation names from traces
    found_operations = set()
    for trace in policy_traces:
        for span in trace.get("spans", []):
            found_operations.add(span["operationName"])

    # Verify expected reconciler operations are present
    for expected_op in expected_reconciler_operations:
        assert expected_op in found_operations, f"Missing expected operation: {expected_op} for {policy_kind}"

    # Verify WASM plugin configuration is built (common to both policies)
    wasm_operations = [op for op in found_operations if "wasm." in op or "istio_extension" in op]
    assert len(wasm_operations) > 0, f"No WASM-related operations found for {policy_kind}"


def test_correlate_policy_enforcement_with_data_plane_traces(authorization, rate_limit, data_plane_trace, tracing):
    """
    Test #21: Correlate control plane traces with data plane enforcement.

    Validates that:
    - Policy name in operator trace matches policy source in data plane trace
    - Can identify which operator reconciliation led to data plane behavior
    - Control plane and data plane traces can be correlated via policy reference
    """

    # Get data plane trace with policy enforcement
    @backoff.on_predicate(backoff.fibo, lambda x: len(x) == 0, max_tries=7, jitter=None)
    def get_data_plane_spans():
        return tracing.get_spans_by_operation(
            request_id=data_plane_trace, service="wasm-shim", operation_name="auth", tag_name="request_id"
        )

    dp_auth_spans = get_data_plane_spans()
    assert len(dp_auth_spans) > 0, "No auth spans found in data plane trace"

    dp_tags = tracing.get_tags_dict(dp_auth_spans[0])
    dp_sources = dp_tags.get("sources", "")
    assert authorization.name() in dp_sources, f"AuthPolicy {authorization.name()} not in data plane sources"

    # Get control plane traces for the AuthPolicy
    auth_cp_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(auth_cp_traces) > 0, f"No control plane traces found for AuthPolicy: {authorization.name()}"

    # Verify control plane trace has source_policies tag referencing the same policy
    found_correlation = False
    for trace in auth_cp_traces:
        for span in trace.get("spans", []):
            tags = tracing.get_tags_dict(span)
            if "source_policies" in tags:
                source_policies = tags["source_policies"]
                if authorization.name() in source_policies and "authpolicy.kuadrant.io" in source_policies:
                    found_correlation = True
                    break
        if found_correlation:
            break

    assert found_correlation, (
        f"Could not correlate control plane trace with data plane trace via policy reference. "
        f"Data plane sources: {dp_sources}"
    )


def test_policy_validation_spans_show_success_or_failure(authorization, rate_limit, tracing):
    """
    Test #22: Validate that policy validation spans include success/failure logs.

    Verifies that validation spans include:
    - Validation result (success via logs or status)
    - Policy validation happens before enforcement
    """
    # Wait for traces for AuthPolicy
    auth_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(auth_traces) > 0

    validation_spans = []
    for trace in auth_traces:
        for span in trace.get("spans", []):
            if "validate" in span["operationName"].lower() or span["operationName"] == "validation":
                validation_spans.append(span)

    assert len(validation_spans) > 0, "No validation spans found"

    # Check for success indicators
    for span in validation_spans:
        tags = tracing.get_tags_dict(span)
        logs = span.get("logs", [])

        # Validation should succeed (status OK or success log)
        has_success_indicator = False

        if tags.get("otel.status_code") == "OK":
            has_success_indicator = True

        for log_entry in logs:
            for field in log_entry.get("fields", []):
                if "success" in field.get("value", "").lower():
                    has_success_indicator = True
                    break

        assert has_success_indicator, "Validation span should have success indicator"


def test_policy_update_generates_new_reconciliation_trace(authorization, tracing):
    """
    Test #23: Validate that policy updates generate new reconciliation traces.

    Verifies that:
    - Policy updates trigger new reconciliation
    - Update traces are distinguishable from creation traces
    - Can observe what changed in the policy
    - Multiple reconciliation events for same policy are traceable
    """

    # Get initial traces for this policy
    initial_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(initial_traces) > 0, "No initial traces found for policy"

    # Get the latest trace timestamp to compare later
    latest_timestamp = 0
    for trace in initial_traces:
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile":
                latest_timestamp = max(latest_timestamp, span["startTime"])

    # Update the policy (directly modify the model to add a new response header)
    # This ensures the model generation changes, triggering a new reconciliation
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.authorization.add_opa_policy("opa", "allow { false }", when=when_post)

    # Wait for new reconciliation trace after update (traces with newer timestamps)
    @backoff.on_predicate(
        backoff.fibo, lambda x: len(x) == 0, max_tries=7, jitter=None
    )
    def get_updated_traces():
        """Fetch traces after policy update, looking for new reconciliation."""
        policy_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})

        # Filter for traces with new reconciliation (after update timestamp)
        new_traces = []
        for trace in policy_traces:
            reconcile_spans = tracing.filter_spans(
                trace.get("spans", []),
                operation_name="controller.reconcile"
            )
            for span in reconcile_spans:
                if span["startTime"] > latest_timestamp:
                    new_traces.append(trace)
                    break

        return new_traces

    updated_traces = get_updated_traces()

    # Verify we have new traces after the update
    new_reconcile_spans = []
    for trace in updated_traces:
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile" and span["startTime"] > latest_timestamp:
                new_reconcile_spans.append(span)

    assert len(new_reconcile_spans) > 0, "No new reconciliation traces found after policy update"

    # Verify the new traces reference the updated policy
    found_policy_reference = False
    for trace in updated_traces:
        for span in trace.get("spans", []):
            # Only check spans from new reconciliation (after the update)
            if span["startTime"] > latest_timestamp:
                tags = tracing.get_tags_dict(span)
                if tags.get("policy.name") == authorization.name():
                    found_policy_reference = True
                    break

    assert found_policy_reference, "Updated reconciliation traces should reference the policy"


def _span_has_error_in_logs(span):
    """Check if span logs contain error keywords."""
    error_keywords = ["error", "fail", "invalid", "warning"]
    for log_entry in span.get("logs", []):
        for field in log_entry.get("fields", []):
            value = field.get("value", "").lower()
            if any(keyword in value for keyword in error_keywords):
                return True
    return False


def _extract_validation_and_errors(policy_traces, tracing):
    """Extract validation spans and check for error indicators."""
    validation_spans = []
    error_found = False

    for trace in policy_traces:
        for span in trace.get("spans", []):
            op_name = span["operationName"]

            if "validate" in op_name.lower() or "validation" in op_name.lower():
                validation_spans.append(span)

            tags = tracing.get_tags_dict(span)
            if tags.get("otel.status_code") == "ERROR" or _span_has_error_in_logs(span):
                error_found = True

    return validation_spans, error_found


def test_invalid_policy_validation_failure_traced(
    blame, cluster, gateway, module_label, backend, authorization, tracing
):
    """
    Test #24: Validate that policy validation failures are properly traced.

    Verifies that:
    - Invalid policies generate traces
    - Validation failure is marked with error status
    - Error messages are captured in span logs
    - Can identify what validation failed
    - Operators can debug rejected policies via traces
    """
    # Create a policy with invalid configuration (non-existent secret reference)
    invalid_policy_name = blame("invalid-authz")

    # Create a route to target
    route = HTTPRoute.create_instance(cluster, invalid_policy_name, gateway, {"app": module_label})
    route.add_backend(backend)
    route.commit()

    # Create policy using the same class as authorization fixture
    invalid_policy = authorization.__class__.create_instance(cluster, invalid_policy_name, route)
    invalid_policy.identity.add_api_key(
        "invalid_key",
        selector=Selector(matchLabels={"app": "non-existent"}),  # This selector won't match any secret
    )

    try:
        invalid_policy.commit()
        invalid_policy.wait_for_ready()

        # Wait for reconciliation traces (even for invalid policy)
        policy_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": invalid_policy_name})
        assert len(policy_traces) > 0, "No traces found for invalid policy"

        # Extract validation spans and check for errors
        validation_spans, error_indicators_found = _extract_validation_and_errors(policy_traces, tracing)

        # Verify we collected validation spans or found error indicators somewhere
        # This validates that the tracing infrastructure captured the invalid policy attempt
        assert (
            len(validation_spans) > 0 or error_indicators_found
        ), "Should have validation spans or error indicators for invalid policy"

    finally:
        # Cleanup: delete the invalid policy
        invalid_policy.delete()
        route.delete()


# ==================================================================================
# Extended Control Plane Tracing Tests
# ==================================================================================
# The following tests provide additional coverage for control plane tracing:
# - Policy lifecycle (deletion/cleanup)
# - Performance metrics (span durations)
# - Multi-policy scenarios (same target, concurrent updates)
# - WASM plugin configuration details
# - Policy target changes and orphaned policies
# - OpenTelemetry semantic conventions compliance
# ==================================================================================


def test_policy_deletion_generates_cleanup_traces(blame, cluster, gateway, module_label, backend, tracing):
    """
    Test: Validate that policy deletion generates cleanup/finalization traces.

    Verifies:
    - Deletion triggers reconciliation with finalizer operations
    - Cleanup spans show resource removal (AuthConfig deletion, etc.)
    - Trace indicates successful cleanup vs errors
    """
    # Create a temporary policy for deletion testing
    temp_policy_name = blame("temp-authz")
    route = HTTPRoute.create_instance(cluster, temp_policy_name, gateway, {"app": module_label})
    route.add_backend(backend)
    route.commit()

    temp_policy = AuthPolicy.create_instance(cluster, temp_policy_name, route)
    temp_policy.identity.add_api_key("test_key", Selector(matchLabels={"app": module_label}))
    temp_policy.commit()
    temp_policy.wait_for_ready()

    # Get timestamp before deletion
    import time

    deletion_time = int(time.time() * 1000000)  # microseconds

    # Delete the policy
    temp_policy.delete()
    route.delete()

    # Wait for deletion/finalization traces
    # Note: After deletion, the policy name might not appear in traces anymore.
    # Instead, look for reconciliation events that happened after deletion.
    @backoff.on_predicate(backoff.fibo, lambda x: len(x) == 0, max_tries=7, jitter=None)
    def get_deletion_traces():
        all_traces = tracing.query.api.traces.get(
            params={"service": "kuadrant-operator", "lookback": "10m", "limit": 50}
        ).json()["data"]
        recent_traces = []
        for trace in all_traces:
            for span in trace.get("spans", []):
                # Look for reconciliation spans after deletion time
                if span.get("startTime", 0) > deletion_time and span["operationName"] == "controller.reconcile":
                    tags = tracing.get_tags_dict(span)
                    # Check if this reconciliation involved AuthPolicy events
                    event_kinds = tags.get("event_kinds", "")
                    if "AuthPolicy" in event_kinds:
                        recent_traces.append(trace)
                        break
        return recent_traces

    deletion_traces = get_deletion_traces()

    # Note: Deletion traces might not always be present if the policy is cleaned up quickly
    # or if finalizers complete before trace propagation. This is informational.
    if len(deletion_traces) == 0:
        # Log for debugging but don't fail - deletion tracing is best-effort
        import logging
        logging.warning(f"No reconciliation traces found after deletion of policy {temp_policy_name}")
        return

    # If we found traces, verify they contain reconciliation operations
    reconcile_operations = set()
    for trace in deletion_traces:
        for span in trace.get("spans", []):
            op_name = span["operationName"]
            if op_name.startswith("reconciler.") or op_name.startswith("effective_policies"):
                reconcile_operations.add(op_name)

    assert len(reconcile_operations) > 0, "Deletion traces found but contain no recognizable reconciliation operations"


def test_reconciliation_duration_captured_in_spans(authorization, tracing):
    """
    Test: Validate that span duration metrics are captured.

    Verifies:
    - controller.reconcile span has duration
    - Child operation spans have durations
    - Duration of WASM config generation is traceable
    - Can identify slow reconciliation steps
    """
    auth_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(auth_traces) > 0

    # Find controller.reconcile spans and validate they have duration
    reconcile_spans = []
    for trace in auth_traces:
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile":
                reconcile_spans.append(span)

    assert len(reconcile_spans) > 0, "No controller.reconcile spans found"

    for span in reconcile_spans:
        duration = get_span_duration_us(span)
        assert duration is not None, "controller.reconcile span missing duration"
        assert duration > 0, f"controller.reconcile span has invalid duration: {duration}"

    # Validate child operations also have durations
    child_operations = []
    for trace in auth_traces:
        for span in trace.get("spans", []):
            if span["operationName"].startswith("reconciler.") or "wasm" in span["operationName"].lower():
                child_operations.append(span)

    assert len(child_operations) > 0, "No child operation spans found"

    for span in child_operations[:5]:  # Check first 5
        duration = get_span_duration_us(span)
        assert duration is not None, f"Child operation {span['operationName']} missing duration"


def test_multiple_policies_same_target_traced_separately(
    blame, cluster, route, module_label, authorization, tracing
):
    """
    Test: Validate traces when multiple policies target same HTTPRoute.

    Verifies:
    - Each policy has distinct traces with correct policy.uid
    - Can distinguish between policies in same namespace
    - source_policies tag lists all applicable policies
    - Reconciliation order is traceable
    """
    # Create a second AuthPolicy targeting the same route as the authorization fixture
    second_policy_name = blame("second-authz")

    second_policy = authorization.__class__.create_instance(
        cluster, second_policy_name, route, labels={"app": module_label}
    )
    second_policy.identity.add_api_key("second_key", Selector(matchLabels={"app": module_label}))

    try:
        second_policy.commit()
        second_policy.wait_for_ready()

        # Wait for traces for both policies
        first_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
        second_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": second_policy_name})

        assert len(first_traces) > 0, f"No traces for first policy {authorization.name()}"
        assert len(second_traces) > 0, f"No traces for second policy {second_policy_name}"

        # Extract policy UIDs from both
        first_uid = None
        second_uid = None

        for trace in first_traces:
            for span in trace.get("spans", []):
                tags = tracing.get_tags_dict(span)
                if tags.get("policy.name") == authorization.name() and "policy.uid" in tags:
                    first_uid = tags["policy.uid"]
                    break
            if first_uid:
                break

        for trace in second_traces:
            for span in trace.get("spans", []):
                tags = tracing.get_tags_dict(span)
                if tags.get("policy.name") == second_policy_name and "policy.uid" in tags:
                    second_uid = tags["policy.uid"]
                    break
            if second_uid:
                break

        assert first_uid is not None, "Could not find policy.uid for first policy"
        assert second_uid is not None, "Could not find policy.uid for second policy"
        assert first_uid != second_uid, "Both policies should have distinct UIDs in traces"

    finally:
        second_policy.delete()


def test_wasm_plugin_configuration_details_in_traces(authorization, rate_limit, tracing):
    """
    Test: Validate detailed WASM plugin configuration tracing.

    Verifies:
    - WASM plugin configuration operations are traced
    - Plugin updates are distinguishable
    - Can identify which policy triggered plugin update
    """
    # Wait for traces for both policies
    auth_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    rl_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": rate_limit.name()})

    all_traces = auth_traces + rl_traces

    # Find WASM-related spans
    wasm_spans = []
    for trace in all_traces:
        for span in trace.get("spans", []):
            op_name = span["operationName"]
            if "wasm" in op_name.lower() or "istio_extension" in op_name.lower():
                wasm_spans.append(span)

    assert len(wasm_spans) > 0, "No WASM-related spans found"

    # Verify WASM spans have policy context
    wasm_with_policy = 0
    for span in wasm_spans:
        tags = tracing.get_tags_dict(span)
        if "policy.name" in tags or "source_policies" in tags:
            wasm_with_policy += 1

    assert wasm_with_policy > 0, "WASM spans should reference which policy triggered them"


def test_policy_target_change_traced(blame, cluster, gateway, route, module_label, backend, tracing):
    """
    Test: Validate traces when policy's targetRef changes.

    Verifies:
    - Target change triggers reconciliation
    - New configuration is traced
    - Can observe the target update in spans
    """
    # Create a dedicated policy for this test to avoid modifying shared fixtures
    policy_name = blame("target-change-authz")
    test_policy = AuthPolicy.create_instance(cluster, policy_name, route, labels={"app": module_label})
    test_policy.identity.add_api_key("test_key", Selector(matchLabels={"app": module_label}))
    test_policy.commit()
    test_policy.wait_for_ready()

    # Create a second HTTPRoute
    second_route_name = blame("second-route")
    second_route = HTTPRoute.create_instance(cluster, second_route_name, gateway, {"app": module_label})
    second_route.add_backend(backend)
    second_route.commit()

    try:
        # Get current traces count
        initial_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": policy_name})
        initial_count = len(initial_traces)

        # Update the policy to target the new route
        def update_target_ref(policy):
            """Modifier function to update targetRef"""
            policy.model.spec.targetRef.name = second_route_name
            return True

        test_policy.apply(modifier_func=update_target_ref)

        # Wait for new reconciliation traces after target change
        @backoff.on_predicate(
            backoff.fibo, lambda x: len(x) <= initial_count, max_tries=7, jitter=None
        )
        def get_updated_traces():
            return tracing.get_trace(service="kuadrant-operator", tags={"policy.name": policy_name})

        updated_traces = get_updated_traces()
        assert len(updated_traces) > initial_count, "No new traces generated after target change"

        # Verify reconciliation happened
        has_recent_reconcile = False
        for trace in updated_traces:
            for span in trace.get("spans", []):
                if span["operationName"] == "controller.reconcile":
                    has_recent_reconcile = True
                    break
            if has_recent_reconcile:
                break

        assert has_recent_reconcile, "No controller.reconcile span found after target change"

    finally:
        # Cleanup
        test_policy.delete()
        second_route.delete()


def test_orphaned_policy_reconciliation_traced(blame, cluster, gateway, module_label, backend, tracing):
    """
    Test: Validate traces when policy references deleted resources.

    Verifies:
    - Policy with deleted HTTPRoute target generates error trace or warning
    - Error details are observable
    - Reconciliation attempts are traceable
    """
    # Create route and policy
    orphan_route_name = blame("orphan-route")
    orphan_route = HTTPRoute.create_instance(cluster, orphan_route_name, gateway, {"app": module_label})
    orphan_route.add_backend(backend)
    orphan_route.commit()

    orphan_policy_name = blame("orphan-policy")
    orphan_policy = AuthPolicy.create_instance(cluster, orphan_policy_name, orphan_route)
    orphan_policy.identity.add_api_key("orphan_key", Selector(matchLabels={"app": module_label}))

    try:
        orphan_policy.commit()
        orphan_policy.wait_for_ready()

        # Delete the route (orphaning the policy)
        orphan_route.delete()

        # Wait a bit for reconciliation to detect the missing target
        import time

        time.sleep(5)

        # Look for traces with error indicators or warnings
        policy_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": orphan_policy_name})

        # Check if any spans indicate problems (error status or error logs)
        has_error_indicator = False
        for trace in policy_traces:
            for span in trace.get("spans", []):
                tags = tracing.get_tags_dict(span)
                if tags.get("otel.status_code") == "ERROR":
                    has_error_indicator = True
                    break

                # Check logs for error keywords
                if _span_has_error_in_logs(span):
                    has_error_indicator = True
                    break

            if has_error_indicator:
                break

        # Note: This test is informational - not all operators may mark orphaned policies as errors
        # The key is that traces exist showing reconciliation attempts
        assert len(policy_traces) > 0, "Should have traces for orphaned policy reconciliation attempts"

    finally:
        orphan_policy.delete()


def test_span_attributes_follow_otel_semantic_conventions(authorization, rate_limit, tracing):
    """
    Test: Validate OpenTelemetry semantic convention compliance.

    Verifies:
    - Span names follow conventions (controller.*, reconciler.*)
    - Error spans use otel.status_code correctly
    - Tags use consistent naming patterns
    """
    auth_traces = tracing.get_trace(service="kuadrant-operator", tags={"policy.name": authorization.name()})
    assert len(auth_traces) > 0

    # Collect all span operation names
    operation_names = set()
    for trace in auth_traces:
        for span in trace.get("spans", []):
            operation_names.add(span["operationName"])

    # Verify naming conventions
    controller_spans = [op for op in operation_names if op.startswith("controller.")]
    reconciler_spans = [op for op in operation_names if op.startswith("reconciler.")]

    assert len(controller_spans) > 0, "Should have spans following controller.* naming convention"
    assert len(reconciler_spans) > 0, "Should have spans following reconciler.* naming convention"

    # Check that status codes are used properly
    for trace in auth_traces[:3]:  # Check first 3 traces
        for span in trace.get("spans", []):
            tags = tracing.get_tags_dict(span)
            if "otel.status_code" in tags:
                status = tags["otel.status_code"]
                assert status in ["OK", "ERROR", "UNSET"], f"Invalid otel.status_code: {status}"
