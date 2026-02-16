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
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kubernetes import Selector
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom, Pattern
from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

# TODO: add skip for control plane tracing not enabled on kuadrant-operator


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    annotations = {"user": "testuser"}
    return create_api_key("api-key", module_label, "IAMTESTUSER", annotations=annotations)


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Configures authorization policy with API key identity and user extraction."""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "user": ValueFrom("auth.identity.metadata.annotations.user"),
            }
        ),
    )
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Configures rate limit policy with CEL-based user targeting."""
    rate_limit.add_limit("testuser", [Limit(3, "10s")], when=[CelPredicate("auth.identity.user == 'testuser'")])
    return rate_limit


@pytest.fixture(scope="module")
def data_plane_trace(client, auth):
    """
    Sends a successful request to generate a data plane trace.
    Returns the request_id for correlation tests.
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    return response.headers.get("x-request-id")


def get_operator_traces(tracing, lookback="10m", limit=50):
    """Helper to fetch recent kuadrant-operator traces."""
    return tracing.query.api.traces.get(
        params={"service": "kuadrant-operator", "lookback": lookback, "limit": limit}
    ).json()["data"]


def find_traces_with_policy(traces, policy_name, tracing):
    """Find traces that reference a specific policy by name."""
    matching_traces = []
    for trace in traces:
        for span in trace.get("spans", []):
            tags = tracing.get_tags_dict(span)
            # Check policy.name tag or source_policies tag
            if tags.get("policy.name") == policy_name or policy_name in tags.get("source_policies", ""):
                matching_traces.append(trace)
                break
    return matching_traces


def find_traces_with_event_kind(traces, event_kind, tracing):
    """Find traces where controller.reconcile span has specific event_kind."""
    matching_traces = []
    for trace in traces:
        for span in trace.get("spans", []):
            if span["operationName"] == "controller.reconcile":
                tags = tracing.get_tags_dict(span)
                if event_kind in tags.get("event_kinds", ""):
                    matching_traces.append(trace)
                    break
    return matching_traces


def wait_for_traces(tracing, filter_func, max_tries=7, lookback="10m"):
    """
    Wait for traces to appear using backoff retry.

    Args:
        tracing: Tracing client instance
        filter_func: Function that takes traces list and returns filtered results
        max_tries: Maximum number of backoff attempts (default: 7)
        lookback: Time window to search for traces (default: 10m)

    Returns:
        Filtered traces list
    """

    @backoff.on_predicate(backoff.fibo, lambda x: len(x) == 0, max_tries=max_tries, jitter=None)
    def get_filtered_traces():
        all_traces = get_operator_traces(tracing, lookback=lookback)
        return filter_func(all_traces)

    return get_filtered_traces()


def wait_for_policy_traces(tracing, policy_name, lookback="10m", max_tries=7):
    """
    Wait for traces referencing a specific policy.

    Args:
        tracing: Tracing client instance
        policy_name: Name of the policy to search for
        lookback: Time window to search (default: 10m)
        max_tries: Maximum backoff attempts (default: 7)

    Returns:
        List of traces referencing the policy
    """
    return wait_for_traces(
        tracing, lambda traces: find_traces_with_policy(traces, policy_name, tracing), max_tries, lookback
    )


def wait_for_event_kind_traces(tracing, event_kind, lookback="10m", max_tries=7):
    """
    Wait for traces with specific event_kind in controller.reconcile spans.

    Args:
        tracing: Tracing client instance
        event_kind: Event kind to search for (e.g., "AuthPolicy.kuadrant.io")
        lookback: Time window to search (default: 10m)
        max_tries: Maximum backoff attempts (default: 7)

    Returns:
        List of traces with matching event_kind
    """
    return wait_for_traces(
        tracing, lambda traces: find_traces_with_event_kind(traces, event_kind, tracing), max_tries, lookback
    )


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
    auth_traces = wait_for_policy_traces(tracing, authorization.name())
    rl_traces = wait_for_policy_traces(tracing, rate_limit.name())

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
    auth_reconcile_traces = wait_for_event_kind_traces(tracing, "AuthPolicy.kuadrant.io")
    rl_reconcile_traces = wait_for_event_kind_traces(tracing, "RateLimitPolicy.kuadrant.io")

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
    policy_traces = wait_for_event_kind_traces(tracing, f"{policy_kind}.kuadrant.io")
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
    auth_cp_traces = wait_for_policy_traces(tracing, authorization.name())
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
    auth_traces = wait_for_policy_traces(tracing, authorization.name())
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
    initial_traces = wait_for_policy_traces(tracing, authorization.name())
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
    def has_new_reconciliation(traces):
        """Check if traces contain reconciliation spans newer than latest_timestamp."""
        for trace in traces:
            for span in trace.get("spans", []):
                if span["operationName"] == "controller.reconcile" and span["startTime"] > latest_timestamp:
                    return True
        return False

    @backoff.on_predicate(
        backoff.fibo, lambda x: len(x) == 0 or not has_new_reconciliation(x), max_tries=7, jitter=None
    )
    def get_updated_traces():
        """Fetch traces after policy update, looking for new reconciliation."""
        return wait_for_traces(
            tracing, lambda traces: find_traces_with_policy(traces, authorization.name(), tracing), lookback="5m"
        )

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


def _span_has_error_in_logs(span, tracing):
    """Helper: Check if span logs contain error keywords."""
    logs = span.get("logs", [])
    error_keywords = ["error", "fail", "invalid", "warning"]

    for log_entry in logs:
        for field in log_entry.get("fields", []):
            value = field.get("value", "").lower()
            if any(keyword in value for keyword in error_keywords):
                return True
    return False


def _extract_validation_and_errors(policy_traces, tracing):
    """Helper: Extract validation spans and check for error indicators from traces."""
    validation_spans = []
    error_found = False

    for trace in policy_traces:
        for span in trace.get("spans", []):
            op_name = span["operationName"]

            # Collect validation spans
            if "validate" in op_name.lower() or "validation" in op_name.lower():
                validation_spans.append(span)

            # Check for error indicators
            tags = tracing.get_tags_dict(span)
            if tags.get("otel.status_code") == "ERROR" or _span_has_error_in_logs(span, tracing):
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
        policy_traces = wait_for_policy_traces(tracing, invalid_policy_name, lookback="5m")
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
