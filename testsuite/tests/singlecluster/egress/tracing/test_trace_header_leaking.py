"""Tests which trace-context headers an egress gateway forwards to an external service.

On ingress, propagating traceparent/tracestate/X-B3-* to your own backends is harmless. On
egress the same behaviour discloses internal trace topology to a third party, so what reaches
the external service is worth asserting explicitly.

No Kuadrant policy is attached here: header propagation is Istio behaviour on a Kuadrant-provisioned
gateway, and leaving the wasm filter out of the path keeps the module fast and the subject narrow.

Validates https://github.com/Kuadrant/kuadrant-operator/pull/2165
"""

import logging

import backoff
import pytest

from testsuite.gateway import RequestHeaderModifierFilter, URLRewriteFilter
from testsuite.gateway import MatchType, PathMatch, RouteMatch
from testsuite.gateway.gateway_api.route import HTTPRoute

from ..conftest import EGRESS_HOSTNAME

pytestmark = [
    pytest.mark.kuadrant_only,
    pytest.mark.egress_gateway,
    pytest.mark.observability,
]

# Trace context defined by W3C (traceparent/tracestate) and B3 (x-b3-*, b3).
# Which of these Envoy emits depends on the configured tracer, so the tests assert on the set.
TRACE_CONTEXT_HEADERS = frozenset(
    {"traceparent", "tracestate", "b3", "x-b3-traceid", "x-b3-spanid", "x-b3-parentspanid", "x-b3-sampled"}
)

STRIP_PATH = "/strip-baggage"


@pytest.fixture(scope="module")
def authorization():
    """No AuthPolicy: this module asserts on Istio header propagation, not policy enforcement"""
    return None


@pytest.fixture(scope="module")
def rate_limit():
    """No RateLimitPolicy: this module asserts on Istio header propagation, not policy enforcement"""
    return None


@pytest.fixture(scope="module")
def route2(request, gateway, cluster, blame, external_service, external_reference, module_label, route, client):
    """Egress HTTPRoute that strips the baggage header before forwarding.

    The route reports Accepted before Envoy has the new config, so requests to its path 503 for
    a moment after commit. The fixture polls the path itself rather than sleeping a fixed time.
    """
    # pylint: disable=unused-argument
    route2 = HTTPRoute.create_instance(cluster, blame("strip-rt"), gateway, {"app": module_label})
    route2.add_hostname(EGRESS_HOSTNAME)
    route2.add_rule(
        external_reference,
        RouteMatch(path=PathMatch(type=MatchType.PATH_PREFIX, value=STRIP_PATH)),
        filters=[
            URLRewriteFilter(hostname=external_service.hostname),
            RequestHeaderModifierFilter(remove=["baggage"]),
        ],
    )
    request.addfinalizer(route2.delete)
    route2.commit()
    route2.wait_for_ready()

    @backoff.on_predicate(backoff.constant, lambda code: code != 200, interval=2, max_tries=15, jitter=None)
    def wait_for_path():
        return client.get(STRIP_PATH).status_code

    assert wait_for_path() == 200, f"Gateway did not start serving {STRIP_PATH}"
    return route2


def received_headers(response):
    """Headers the external service saw, as echoed back by the MockServer echo expectation"""
    assert response.status_code == 200, f"Expected the egress request to succeed, got {response.status_code}"
    return {name.lower() for name in response.json()["headers"]}


def test_trace_context_reaches_external_service(client):
    """
    Test that trace context headers are forwarded to the external service by default.

    This is the disclosure the guide warns about, and it is also the control for the
    disableContextPropagation tests: without it, those would pass trivially on a cluster where
    tracing happens to be misconfigured.

    The client deliberately sends no traceparent of its own - otherwise this would only prove
    that Envoy forwards a header it was handed, not that it injects trace context itself.
    """
    headers = received_headers(client.get("/get"))

    leaked = TRACE_CONTEXT_HEADERS & headers
    logging.info("Trace context headers that reached the external service: %s", sorted(leaked))
    assert leaked, (
        f"No trace context header reached the external service. Expected Envoy to inject at least "
        f"one of {sorted(TRACE_CONTEXT_HEADERS)}, got {sorted(headers)}"
    )


def test_baggage_reaches_external_service(client):
    """
    Test that a baggage header is forwarded to the external service.

    baggage is not part of trace context, so disableContextPropagation does not cover it. This
    pins the starting state that makes that gap visible.
    """
    headers = received_headers(client.get("/get", headers={"baggage": "userId=alice"}))

    assert "baggage" in headers, f"baggage did not reach the external service, got {sorted(headers)}"


def test_request_header_modifier_strips_baggage(client, route2):  # pylint: disable=unused-argument
    """
    Test that an HTTPRoute RequestHeaderModifier removes baggage before it leaves the gateway.

    This is the documented mitigation for baggage, and the only one available below Istio 1.30,
    where disableContextPropagation does not exist.
    """
    headers = received_headers(client.get(STRIP_PATH, headers={"baggage": "userId=alice"}))

    assert "baggage" not in headers, f"baggage reached the external service despite the filter: {sorted(headers)}"
