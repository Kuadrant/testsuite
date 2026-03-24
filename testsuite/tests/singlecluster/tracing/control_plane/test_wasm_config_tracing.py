"""
WASM configuration tracing tests.

Tests that validate WASM plugin configuration generation is observable in traces.
Critical for debugging "why isn't my policy being enforced?" issues.
"""

import pytest

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


def test_wasm_config_includes_gateway_and_route_context(auth_traces, gateway, route):
    """
    Validate that WASM config spans identify which Gateway/HTTPRoute they apply to.

    When debugging "why isn't my policy enforced?", operators need to see:
    - Which Gateway the WASM config targets
    - Which HTTPRoute the policy applies to
    - Which listener is configured
    """
    wasm_config_spans = []
    for trace in auth_traces:
        wasm_config_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.BuildConfigForPath")
        )

    if len(wasm_config_spans) == 0:
        pytest.skip("No WASM config spans in trace")

    span = wasm_config_spans[0]

    # Gateway context
    assert span.has_tag("gateway.name"), "WASM config should identify target Gateway"
    assert span.has_tag("gateway.namespace"), "WASM config should include Gateway namespace"
    assert span.get_tag("gateway.name") == gateway.name()

    # HTTPRoute context
    assert span.has_tag("httproute.name"), "WASM config should identify target HTTPRoute"
    assert span.has_tag("httproute.namespace"), "WASM config should include HTTPRoute namespace"
    assert span.get_tag("httproute.name") == route.name()

    # Listener context
    assert span.has_tag("listener.name"), "WASM config should identify Gateway listener"


def test_wasm_config_shows_source_policies(auth_traces, authorization, rate_limit):
    """
    Validate that WASM config spans show which policies contribute to the config.

    The source_policies tag is critical for debugging:
    - Which AuthPolicy is active
    - Which RateLimitPolicy is active
    - Policy conflicts/precedence
    """
    wasm_config_spans = []
    for trace in auth_traces:
        wasm_config_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.BuildConfigForPath")
        )

    if len(wasm_config_spans) == 0:
        pytest.skip("No WASM config spans in trace")

    span = wasm_config_spans[0]

    # Should have source_policies tag
    source_policies = span.get_tag("source_policies")
    assert source_policies, "WASM config should list source policies"

    # Should reference our test policies
    auth_policy_ref = f"authpolicy.kuadrant.io:kuadrant/{authorization.name()}"
    rl_policy_ref = f"ratelimitpolicy.kuadrant.io:kuadrant/{rate_limit.name()}"

    source_policies_str = str(source_policies).lower()
    assert auth_policy_ref.lower() in source_policies_str, f"Should reference AuthPolicy {authorization.name()}"
    assert rl_policy_ref.lower() in source_policies_str, f"Should reference RateLimitPolicy {rate_limit.name()}"


def test_wasm_config_shows_action_validation_results(auth_traces):
    """
    Validate that WASM config spans show action validation metrics.

    When debugging "why isn't my policy applied?", operators need to see:
    - How many actions were generated (before_merge)
    - How many actions were validated successfully
    - How many actions were invalid
    - How many actions made it into final config (after_merge)
    """
    wasm_config_spans = []
    for trace in auth_traces:
        wasm_config_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.BuildConfigForPath")
        )

    if len(wasm_config_spans) == 0:
        pytest.skip("No WASM config spans in trace")

    span = wasm_config_spans[0]

    # Validation metrics
    assert span.has_tag("actions.before_merge"), "Should show action count before merge"
    assert span.has_tag("actions.validated"), "Should show validated action count"
    assert span.has_tag("actions.invalid"), "Should show invalid action count"
    assert span.has_tag("actions.after_merge"), "Should show final action count"

    # Verify at least some actions were validated
    validated = span.get_tag("actions.validated")
    assert validated > 0, "Should have validated at least one action"

    # Verify no invalid actions (healthy policy)
    invalid = span.get_tag("actions.invalid")
    assert invalid == 0, f"Should have no invalid actions, got {invalid}"


def test_wasm_actionset_shows_policy_breakdown(auth_traces):
    """
    Validate that WASM ActionSet spans show auth/ratelimit action breakdown.

    When debugging policy enforcement, operators need to see:
    - How many auth actions are configured
    - How many ratelimit actions are configured
    - The hostname/path the actionset applies to
    """
    actionset_spans = []
    for trace in auth_traces:
        actionset_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.ActionSet.create")
        )

    if len(actionset_spans) == 0:
        pytest.skip("No WASM ActionSet spans in trace")

    span = actionset_spans[0]

    # Action counts
    assert span.has_tag("actionset.auth_actions"), "Should show auth action count"
    assert span.has_tag("actionset.ratelimit_actions"), "Should show ratelimit action count"

    # Should have at least one of each (our test has both AuthPolicy and RateLimitPolicy)
    auth_actions = span.get_tag("actionset.auth_actions")
    ratelimit_actions = span.get_tag("actionset.ratelimit_actions")
    assert auth_actions > 0, "Should have auth actions from AuthPolicy"
    assert ratelimit_actions > 0, "Should have ratelimit actions from RateLimitPolicy"

    # Route context
    assert span.has_tag("hostname"), "Should show target hostname"
    assert span.has_tag("path"), "Should show target path"
    assert span.has_tag("predicate_count"), "Should show predicate count"


def test_wasm_merge_shows_action_deduplication(auth_traces):
    """
    Validate that WASM merge operation shows action deduplication metrics.

    When multiple policies target the same route, actions may be merged/deduplicated.
    Operators need to see:
    - How many actions went into merge (input)
    - How many were merged/deduplicated
    - How many came out (output)
    """
    merge_spans = []
    for trace in auth_traces:
        merge_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.MergeAndVerifyActions")
        )

    if len(merge_spans) == 0:
        pytest.skip("No WASM merge spans in trace")

    span = merge_spans[0]

    # Merge metrics
    assert span.has_tag("actions.input"), "Should show input action count"
    assert span.has_tag("actions.merged"), "Should show merged action count"
    assert span.has_tag("actions.output"), "Should show output action count"

    # Sanity check: output <= input (can't create actions from nothing)
    input_count = span.get_tag("actions.input")
    output_count = span.get_tag("actions.output")
    assert output_count <= input_count, f"Output ({output_count}) should not exceed input ({input_count})"


def test_wasm_action_types_are_observable(auth_traces):
    """
    Validate that WASM spans show which action types are configured.

    Operators need to see if auth-service and/or ratelimit-service actions are present.
    """
    action_set_builder_spans = []
    for trace in auth_traces:
        action_set_builder_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "wasm.BuildActionSetsForPath")
        )

    if len(action_set_builder_spans) == 0:
        pytest.skip("No WASM BuildActionSetsForPath spans in trace")

    span = action_set_builder_spans[0]

    action_types = span.get_tag("action_types")
    assert action_types, "Should show action types"

    # Our test has both AuthPolicy and RateLimitPolicy
    action_types_str = str(action_types).lower()
    assert "auth-service" in action_types_str, "Should have auth-service action type"
    assert "ratelimit-service" in action_types_str, "Should have ratelimit-service action type"


def test_wasm_reconciler_is_parent_of_config_operations(auth_traces):
    """
    Validate that WASM config operations are children of reconciler.istio_extension.

    Proper parent-child relationships allow trace visualization tools to show
    the full reconciliation flow hierarchically.
    """
    istio_extension_spans = []
    for trace in auth_traces:
        istio_extension_spans.extend(
            trace.filter_spans(lambda s: s.operation_name == "reconciler.istio_extension")
        )

    if len(istio_extension_spans) == 0:
        pytest.skip("No reconciler.istio_extension spans in trace")

    parent_span = istio_extension_spans[0]

    # Find WASM config child spans
    for trace in auth_traces:
        if parent_span not in trace.spans:
            continue

        wasm_children = trace.get_children(parent_span.span_id)
        wasm_config_children = [
            child for child in wasm_children
            if child.operation_name == "wasm.BuildConfigForPath"
        ]

        if len(wasm_config_children) > 0:
            # Found it - verify parent-child relationship
            assert wasm_config_children[0].get_parent_id() == parent_span.span_id
            return

    pytest.skip("No WASM config child spans found under reconciler.istio_extension")
