"""
Tests for distributed tracing integration across Kuadrant components.

This module validates that tracing correctly captures request flows through the entire
Kuadrant stack, including wasm-shim, Authorino, Limitador, and gateway services.
"""

import os
import pytest

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.data_plane]


@pytest.fixture(scope="module")
def trace_request_ids(client, auth):
    """
    Sends requests producing 200 and 429 responses.

    Both are generated together because they share rate limit state:
    the 200 request consumes 1 of 3 allowed, 2 more exhaust the limit, and the next triggers 429.
    """
    response_200 = client.get(
        "/get", auth=auth, headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"}
    )
    assert response_200.status_code == 200

    responses = client.get_many("/get", 2, auth=auth)
    responses.assert_all(200)

    response_429 = client.get(
        "/get", auth=auth, headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"}
    )
    assert response_429.status_code == 429

    return (
        response_200.headers.get("x-request-id"),
        response_429.headers.get("x-request-id"),
    )


@pytest.fixture(scope="module")
def trace_200(trace_request_ids, tracing):
    """Fetches and caches the full wasm-shim trace for the 200 response."""
    request_id = trace_request_ids[0]
    traces = tracing.get_traces(service="wasm-shim", min_processes=4, tags={"request_id": request_id})
    assert len(traces) == 1, f"No trace was found in tracing backend with request_id: {request_id}"
    return traces[0]


@pytest.fixture(scope="module")
def trace_429(trace_request_ids, tracing):
    """Fetches and caches the full wasm-shim trace for the 429 response."""
    request_id = trace_request_ids[1]
    traces = tracing.get_traces(service="wasm-shim", min_processes=4, tags={"request_id": request_id})
    assert len(traces) == 1, f"No trace was found in tracing backend with request_id: {request_id}"
    return traces[0]


@pytest.fixture(scope="module")
def trace_401(client, tracing):
    """
    Sends request producing 401 response and fetches the full wasm-shim trace"""
    response_401 = client.get("/get", headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"})
    assert response_401.status_code == 401

    request_id = response_401.headers.get("x-request-id")
    traces = tracing.get_traces(service="wasm-shim", min_processes=3, tags={"request_id": request_id})
    assert len(traces) == 1, f"No trace was found in tracing backend with request_id: {request_id}"
    return traces[0]


def test_trace_includes_all_kuadrant_services(trace_200, label):
    """
    Test that distributed tracing captures all Kuadrant components in a single trace.

    Verifies that a request flowing through the system generates a complete distributed
    trace with all expected service processes:
    - wasm-shim: WASM plugin processing requests
    - authorino: Authorization service
    - limitador: Rate limiting service
    - gateway: Istio/Envoy gateway service
    """

    process_services = trace_200.get_process_services()

    services = ["wasm-shim", "authorino", "limitador", f"{label}.kuadrant"]
    for service in services:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"


def test_relevant_services_on_auth_denied(trace_401, label):
    """
    Test that auth-denied traces only include services up to the authorization step.

    When a request is rejected with 401, the trace should contain wasm-shim and authorino
    but not limitador, since the request is short-circuited before reaching the rate limiter.
    Note: gateway service is not included since the request was sent without traceparent header.
    """

    process_services = trace_401.get_process_services()

    services = ["wasm-shim", "authorino", f"{label}.kuadrant"]
    for service in services:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"

    assert (
        "limitador" not in process_services
    ), f"'limitador' should not be in trace when auth is denied: {process_services}"


@pytest.mark.parametrize(
    "operation_name, policy, policy_kind",
    [
        ("auth", "authorization", "authpolicy"),
        ("ratelimit", "rate_limit", "ratelimitpolicy"),
    ],
)
def test_spans_have_correct_policy_source_references(trace_200, operation_name, policy, policy_kind, request):
    """
    Test that trace spans contain correct policy source references.

    Validates that authorization and rate limiting spans include a "sources" tag
    that references the specific Kuadrant policy (AuthPolicy or RateLimitPolicy)
    responsible for the operation. This enables operators to trace policy enforcement
    back to specific policy resources.

    Parametrized to test both:
    - auth spans → AuthPolicy source reference
    - ratelimit spans → RateLimitPolicy source reference
    """
    policy_obj = request.getfixturevalue(policy)
    expected_sources = f"{policy_kind}.kuadrant.io:kuadrant/{policy_obj.model.metadata['name']}"
    policy_spans = trace_200.filter_spans(
        lambda s: s.operation_name == operation_name and s.has_tag("sources", expected_sources)
    )
    assert len(policy_spans) > 0, f"No {operation_name} span with sources '{expected_sources}' found in trace"


@pytest.mark.parametrize("expected_status_code, trace_fixture", [(429, "trace_429"), (401, "trace_401")])
def test_send_reply_span_on_request_rejection(expected_status_code, trace_fixture, request):
    """
    Test that send_reply spans capture correct metadata for request rejections.

    Validates that when requests are rejected (401 unauthorized, 429 rate limited),
    the send_reply span includes the correct status_code tag for observability.
    This allows operators to trace and debug rejection scenarios through distributed
    tracing.

    Parametrized to test:
    - 429 rate_limit: Request exceeds rate limit (after 3 successful requests)
    - 401 auth_failure: Request without valid authentication
    """
    trace = request.getfixturevalue(trace_fixture)
    send_reply_spans = trace.filter_spans(
        lambda s: s.operation_name == "send_reply" and s.has_tag("status_code", expected_status_code)
    )
    assert len(send_reply_spans) > 0, f"No send_reply span with status_code {expected_status_code} found in trace"


def test_send_reply_span_not_on_successful_response(trace_200):
    """
    Test that send_reply span is not present for successful (200) responses.

    The send_reply span is only generated when the wasm-shim rejects a request
    (e.g., 401 or 429). For successful responses that pass through all policies,
    no send_reply span should be emitted.
    """
    send_reply_spans = trace_200.filter_spans(lambda s: s.operation_name == "send_reply")
    assert (
        len(send_reply_spans) == 0
    ), f"Expected no send_reply spans for successful response, but found {len(send_reply_spans)}"


def assert_parent_child(trace, parent_op, child_op):
    """Assert that child_op span is a direct child of parent_op span."""
    parent_span = trace.filter_spans(lambda s: s.operation_name == parent_op)[0]
    child_span = trace.filter_spans(lambda s: s.operation_name == child_op)[0]
    parent_id = child_span.get_parent_id()
    assert (
        parent_id == parent_span.span_id
    ), f"Expected '{child_op}' to be a child of '{parent_op}', but got parent {parent_id}"


def test_span_hierarchy(trace_200):
    """
    Test that spans in a successful (200) trace form the expected parent-child hierarchy.
    Validates parent-child relationships between spans across wasm-shim, authorino, and limitador.
    """

    spans = trace_200.spans
    assert len(spans) > 0, "No spans found in trace"

    expected_operations_hierarchy = {
        "kuadrant_filter": ["auth", "ratelimit"],
        "auth": ["auth_request", "auth_response"],
        "ratelimit": ["ratelimit_request", "ratelimit_response"],
        "auth_request": ["envoy.service.auth.v3.Authorization/Check"],
        "envoy.service.auth.v3.Authorization/Check": ["Check"],
        "ratelimit_request": ["should_rate_limit"],
        "should_rate_limit": ["check_and_update"],
    }

    for parent_op, child_ops in expected_operations_hierarchy.items():
        parent_spans = [s for s in trace_200.spans if s.operation_name == parent_op]
        assert parent_spans, f"Expected operation '{parent_op}' not found in trace spans"
        for child_op in child_ops:
            child_spans = [s for s in trace_200.spans if s.operation_name == child_op]
            assert child_spans, f"Expected operation '{child_op}' not found in trace spans"
            assert_parent_child(trace_200, parent_op, child_op)
