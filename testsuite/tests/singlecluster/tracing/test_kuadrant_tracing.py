"""
Tests for distributed tracing integration across Kuadrant components.

This module validates that tracing correctly captures request flows through the entire
Kuadrant stack, including wasm-shim, Authorino, Limitador, and gateway services.
"""

import os
import pytest
import backoff

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


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


@pytest.fixture(scope="function")
def rate_limit(rate_limit):
    """Configures rate limit policy with CEL-based user targeting."""
    rate_limit.add_limit("testuser", [Limit(3, "10s")], when=[CelPredicate("auth.identity.user == 'testuser'")])
    return rate_limit


@pytest.fixture(scope="function", autouse=True)
def commit(request, authorization, rate_limit):
    """
    Commits authorization and rate limit policies before each test.

    Function-scoped to work with the function-scoped rate_limit fixture,
    ensuring each test has a fresh rate limit policy. Authorization is
    re-committed to guarantee it's enforced before rate_limit (which depends
    on auth.identity.user in its CEL expression).
    """
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()


def test_trace_includes_all_kuadrant_services(client, auth, tracing, label):
    """
    Test that distributed tracing captures all Kuadrant components in a single trace.

    Verifies that a request flowing through the system generates a complete distributed
    trace with all expected service processes:
    - wasm-shim: WASM plugin processing requests
    - authorino: Authorization service
    - limitador: Rate limiting service
    - gateway: Istio/Envoy gateway service

    Note: traceparent header is required to link gateway/istio traces with wasm-shim traces
    in a single distributed trace. Without it, wasm-shim starts its own trace (with authorino
    and limitador as children), but the gateway trace remains separate due to Istio not passing
    its trace ID to the WASM plugin
    """
    response = client.get(
        "/get", auth=auth, headers={"Traceparent": f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"}
    )
    request_id = response.headers.get("x-request-id")
    assert response.status_code == 200

    @backoff.on_predicate(backoff.fibo, lambda x: len(x) == 0 or len(x[0]["processes"]) < 4, max_tries=5, jitter=None)
    def get_full_trace():
        """Get trace and retry until all 4 processes are present"""
        return tracing.get_trace(service="wasm-shim", request_id=request_id, tag_name="request_id")

    trace = get_full_trace()
    assert len(trace) == 1, f"No trace was found in tracing backend with request_id: {request_id}"

    processes = trace[0]["processes"]
    process_services = {process["serviceName"] for process in processes.values()}

    services = ["wasm-shim", "authorino", "limitador", f"{label}.kuadrant"]
    for service in services:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"


@pytest.mark.parametrize(
    "operation_name, policy, policy_kind",
    [
        ("auth", "authorization", "authpolicy"),
        ("ratelimit", "rate_limit", "ratelimitpolicy"),
    ],
)
def test_spans_have_correct_policy_source_references(
    client, auth, tracing, operation_name, policy, policy_kind, request
):
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
    response = client.get("/get", auth=auth)
    request_id = response.headers.get("x-request-id")
    assert response.status_code == 200

    policy_spans = tracing.get_spans_by_operation(
        request_id=request_id, service="wasm-shim", operation_name=operation_name, tag_name="request_id"
    )
    assert len(policy_spans) > 0, f"No {operation_name} span found in trace"

    span = policy_spans[0]
    tags = tracing.get_tags_dict(span)
    sources_value = tags["sources"].strip('[]"')
    policy_obj = request.getfixturevalue(policy)
    expected_sources = f"{policy_kind}.kuadrant.io:kuadrant/{policy_obj.model.metadata['name']}"
    assert sources_value == expected_sources, f"Expected sources to be '{expected_sources}' but got '{sources_value}'"


@pytest.mark.parametrize(
    "expected_status_code, scenario",
    [
        (429, "rate_limit"),
        (401, "auth_failure"),
    ],
)
def test_send_reply_span_on_request_rejection(client, auth, tracing, expected_status_code, scenario):
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
    if scenario == "rate_limit":
        responses = client.get_many(
            "/get",
            3,
            auth=auth,
        )
        responses.assert_all(200)
        response = client.get("/get", auth=auth)
    else:
        response = client.get(
            "/get",
        )

    assert response.status_code == expected_status_code
    request_id = response.headers.get("x-request-id")

    send_reply_spans = tracing.get_spans_by_operation(
        request_id=request_id, service="wasm-shim", operation_name="send_reply", tag_name="request_id"
    )
    assert len(send_reply_spans) > 0

    span = send_reply_spans[0]
    tags = tracing.get_tags_dict(span)
    status_code_tag = tags["status_code"]
    assert str(status_code_tag) == str(
        expected_status_code
    ), f"Expected status_code {expected_status_code} in send_reply span, got {tags['status_code']}"
