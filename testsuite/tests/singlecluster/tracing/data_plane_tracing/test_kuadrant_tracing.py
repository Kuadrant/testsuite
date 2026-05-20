"""
Tests for distributed tracing integration across Kuadrant components.

This module validates that tracing correctly captures request flows through the entire
Kuadrant stack, including wasm-shim, Authorino, Limitador, and gateway services.
"""

import os
import pytest

pytestmark = [
    pytest.mark.observability,
    pytest.mark.limitador,
    pytest.mark.authorino,
    pytest.mark.kuadrant_only,
]


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
    "action, policy, policy_kind",
    [
        ("auth", "authorization", "authpolicy"),
        ("ratelimit", "rate_limit", "ratelimitpolicy"),
    ],
)
def test_spans_have_correct_policy_source_references(trace_200, action, policy, policy_kind, request):
    """
    Test that trace spans contain correct policy source references.

    Validates that authorization and rate limiting grpc spans include a "sources" tag
    that references the specific Kuadrant policy (AuthPolicy or RateLimitPolicy)
    responsible for the operation. This enables operators to trace policy enforcement
    back to specific policy resources.

    Parametrized to test both:
    - auth grpc spans → AuthPolicy source reference
    - ratelimit grpc spans → RateLimitPolicy source reference
    """
    policy_obj = request.getfixturevalue(policy)
    expected_sources = f"{policy_kind}.kuadrant.io:kuadrant/{policy_obj.model.metadata['name']}"
    policy_spans = trace_200.filter_spans(
        lambda s: s.operation_name == "grpc" and s.has_tag("action", action) and s.has_tag("sources", expected_sources)
    )
    assert len(policy_spans) > 0, f"No grpc span with action '{action}' and sources '{expected_sources}' found in trace"


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


@pytest.mark.parametrize(
    "expected_limited, trace_fixture",
    [
        (False, "trace_200"),
        (True, "trace_429"),
    ],
)
def test_ratelimit_limited_tag(expected_limited, trace_fixture, request):
    """
    Test that the should_rate_limit span has the correct ratelimit.limited tag.

    When a request is allowed (200), ratelimit.limited should be false.
    When a request is rate limited (429), ratelimit.limited should be true.
    """
    trace = request.getfixturevalue(trace_fixture)
    srl_spans = trace.filter_spans(
        lambda s: s.operation_name == "should_rate_limit" and s.has_tag("ratelimit.limited", expected_limited)
    )
    assert len(srl_spans) > 0, f"No should_rate_limit span with ratelimit.limited={expected_limited} found in trace"


def test_ratelimit_limit_name_tag(trace_429, rate_limit):
    """
    Test that the should_rate_limit span has the correct ratelimit.limit_name tag
    matching the limit name configured in the RateLimitPolicy.
    """
    limit_name = list(rate_limit.model.spec.limits)[0]
    srl_spans = trace_429.filter_spans(
        lambda s: s.operation_name == "should_rate_limit" and s.has_tag("ratelimit.limit_name", limit_name)
    )
    assert len(srl_spans) > 0, f"No should_rate_limit span with ratelimit.limit_name='{limit_name}' found in trace"


def assert_child(trace, parent_span, child_op, **tags):
    """Assert that parent_span has a direct child with the given operation name and tags. Returns the child span."""
    children = trace.get_children(parent_span.span_id)
    matches = [c for c in children if c.operation_name == child_op]
    for key, value in tags.items():
        matches = [c for c in matches if c.has_tag(key, value)]
    assert len(matches) == 1, (
        f"Expected exactly one '{child_op}' child of '{parent_span.operation_name}' "
        f"(tags={tags}), found {len(matches)}"
    )
    return matches[0]


def test_span_hierarchy(trace_200):
    """
    Test that spans in a successful (200) trace form the expected parent-child hierarchy.
    Validates parent-child relationships between spans across wasm-shim, authorino, and limitador.
    """

    assert len(trace_200.spans) > 0, "No spans found in trace"

    kuadrant_filters = trace_200.filter_spans(lambda s: s.operation_name == "kuadrant_filter")
    assert kuadrant_filters, "No 'kuadrant_filter' span found in trace"
    kuadrant_filter = kuadrant_filters[0]

    # Auth grpc span and its children
    auth_grpc = assert_child(trace_200, kuadrant_filter, "grpc", action="auth")
    auth_req = assert_child(trace_200, auth_grpc, "grpc_request", grpc_service="envoy.service.auth.v3.Authorization")
    assert_child(trace_200, auth_grpc, "grpc_response", grpc_service="envoy.service.auth.v3.Authorization")
    auth_check = assert_child(trace_200, auth_req, "envoy.service.auth.v3.Authorization/Check")
    assert_child(trace_200, auth_check, "Check")

    # Ratelimit grpc span and its children
    rl_grpc = assert_child(trace_200, kuadrant_filter, "grpc", action="ratelimit")
    rl_req = assert_child(
        trace_200, rl_grpc, "grpc_request", grpc_service="envoy.service.ratelimit.v3.RateLimitService"
    )
    assert_child(trace_200, rl_grpc, "grpc_response", grpc_service="envoy.service.ratelimit.v3.RateLimitService")
    should_rate_limit = assert_child(trace_200, rl_req, "should_rate_limit")
    assert_child(trace_200, should_rate_limit, "check_and_update")

    # Headers span
    assert_child(trace_200, kuadrant_filter, "headers")
