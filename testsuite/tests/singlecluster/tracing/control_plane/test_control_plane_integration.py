"""
Cross-plane integration tracing tests.

Tests correlation between control plane and data plane traces, and WASM plugin configuration.
"""

import pytest

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def data_plane_request(client, auth):
    """
    Sends a successful request to generate a data plane trace.
    Returns the request_id for correlation tests.
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    return response.headers.get("x-request-id")


@pytest.fixture(scope="module")
def data_plane_auth_spans(data_plane_request, tracing):
    """Fetches auth spans from data plane trace."""
    traces = tracing.get_traces(service="wasm-shim", tags={"request_id": data_plane_request})
    assert len(traces) > 0, "No data plane traces found"

    spans = []
    for trace in traces:
        spans.extend(trace.filter_spans(operation_name="auth"))

    assert len(spans) > 0, "No auth spans found in data plane trace"
    return spans


def test_correlate_policy_enforcement_with_data_plane_traces(
    authorization, data_plane_auth_spans, auth_traces
):
    """
    Correlate control plane traces with data plane enforcement.

    Validates that:
    - Policy name in operator trace matches policy source in data plane trace
    - Can identify which operator reconciliation led to data plane behavior
    - Control plane and data plane traces can be correlated via policy reference
    """
    # Verify data plane auth span has correct sources tag
    dp_sources = data_plane_auth_spans[0].get_tag("sources", "")
    assert f"authpolicy.kuadrant.io:kuadrant/{authorization.name()}" in dp_sources, (
        f"AuthPolicy {authorization.name()} not in data plane sources"
    )

    # Verify control plane traces exist for the same policy
    assert len(auth_traces) > 0, "No control plane traces found for AuthPolicy"

    # Verify control plane traces reference the correct policy
    policy_spans = []
    for trace in auth_traces:
        policy_spans.extend(
            trace.filter_spans(predicate=lambda s: s.has_tag("policy.name", authorization.name()))
        )

    assert len(policy_spans) > 0, (
        f"Control plane traces do not reference policy {authorization.name()}. "
        f"Data plane sources: {dp_sources}"
    )


def test_wasm_plugin_configuration_details_in_traces(auth_traces, rl_traces):
    """
    Test: Validate detailed WASM plugin configuration tracing.

    Verifies:
    - WASM plugin configuration operations are traced
    - Plugin updates are distinguishable
    - Can identify which policy triggered plugin update
    """
    all_traces = auth_traces + rl_traces

    # Find WASM-related spans
    wasm_spans = []
    for trace in all_traces:
        wasm_spans.extend(
            trace.filter_spans(
                predicate=lambda s: "wasm" in s.operation_name.lower() or "istio_extension" in s.operation_name.lower()
            )
        )

    assert len(wasm_spans) > 0, "No WASM-related spans found"

    # Verify WASM spans have policy context
    wasm_with_policy_spans = [
        span for span in wasm_spans if span.has_tag("policy.name") or span.has_tag("source_policies")
    ]

    assert len(wasm_with_policy_spans) > 0, "WASM spans should reference which policy triggered them"
