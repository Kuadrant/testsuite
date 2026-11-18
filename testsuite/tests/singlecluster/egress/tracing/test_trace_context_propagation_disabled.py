"""Tests that Istio's disableContextPropagation stops trace context reaching an external service.

This is the mitigation the egress guide recommends for the disclosure demonstrated in
test_trace_header_leaking.py. It must suppress outbound trace headers without switching off span
reporting - conflating the two with disableSpanReporting is the obvious implementation mistake,
so both halves are asserted.

Gated on the Telemetry CRD actually accepting the field rather than on an Istio version: the
schema is what the API server validates against, and it stays correct when a vendor backports
the feature into an older stream.

Validates https://github.com/Kuadrant/kuadrant-operator/pull/2165
"""

import pytest

from testsuite.kubernetes.istio.telemetry import Telemetry

from ..conftest import wait_until_serving
from .test_trace_header_leaking import TRACE_CONTEXT_HEADERS, received_headers

pytestmark = [
    pytest.mark.kuadrant_only,
    pytest.mark.egress_gateway,
    pytest.mark.observability,
]


@pytest.fixture(scope="module", autouse=True)
def require_context_propagation_support(cluster, skip_or_fail):
    """Skip unless the Telemetry CRD accepts disableContextPropagation (Istio 1.30+)"""
    if not Telemetry.supports_field(cluster, "disableContextPropagation"):
        skip_or_fail("Telemetry CRD does not support disableContextPropagation")


@pytest.fixture(scope="module")
def authorization():
    """No AuthPolicy: this module asserts on Istio header propagation, not policy enforcement"""
    return None


@pytest.fixture(scope="module")
def rate_limit():
    """No RateLimitPolicy: this module asserts on Istio header propagation, not policy enforcement"""
    return None


@pytest.fixture(scope="module", autouse=True)
def telemetry(request, cluster, blame, gateway, module_label, route, client):
    """Telemetry disabling trace context propagation on the egress gateway only.

    providers and randomSamplingPercentage are repeated from the root default-telemetry on
    purpose. Istio resolves Telemetry by hierarchy with the workload-scoped resource overriding,
    so omitting them risks losing the provider or dropping sampling to the 1% default and
    failing the span-reporting assertion for the wrong reason.
    """
    # pylint: disable=unused-argument
    telemetry = Telemetry.create_instance(
        cluster,
        blame("no-ctx-prop"),
        tracing=[
            {
                "providers": [{"name": "jaeger-otlp"}],
                "randomSamplingPercentage": 100.0,
                "disableContextPropagation": True,
            }
        ],
        gateway_name=gateway.name(),
        labels={"app": module_label},
    )
    request.addfinalizer(telemetry.delete)
    telemetry.commit()

    # Applying a Telemetry rewrites the gateway's tracing config, and Envoy 503s while
    # that push lands. Settle before any test sends its request.
    wait_until_serving(client)
    return telemetry


def test_trace_context_does_not_reach_external_service(client):
    """
    Test that no trace context header reaches the external service once propagation is disabled.

    The inverse of test_trace_context_reaches_external_service, which establishes that these
    headers do arrive without the Telemetry in place.
    """
    headers = received_headers(client.get("/get"))

    leaked = TRACE_CONTEXT_HEADERS & headers
    assert not leaked, f"Trace context still reached the external service: {sorted(leaked)}"


def test_baggage_still_reaches_external_service(client):
    """
    Test that baggage is unaffected by disableContextPropagation.

    baggage is not trace context, so the mitigation does not cover it and it remains a
    disclosure path that has to be closed separately with a RequestHeaderModifier.
    """
    headers = received_headers(client.get("/get", headers={"baggage": "userId=alice"}))

    assert "baggage" in headers, f"baggage no longer reaches the external service, got {sorted(headers)}"


@pytest.mark.user_managed_istio
def test_envoy_spans_are_still_reported(client, tracing, module_label, cluster):
    """
    Test that the gateway still reports spans while context propagation is disabled.

    disableContextPropagation must suppress outbound headers only. If it were conflated with
    disableSpanReporting the Envoy trace would vanish, which this catches.
    """
    response = client.get("/get")
    assert response.status_code == 200, f"Expected the egress request to succeed, got {response.status_code}"

    # Read the id the external service saw: with no policy attached there is no wasm filter to
    # echo x-request-id back on the response, but Envoy still sets it on the forwarded request.
    request_id = response.json()["headers"].get("x-request-id")
    assert request_id is not None, "Envoy did not set x-request-id on the forwarded request"

    envoy_service = f"{module_label}.{cluster.project}"
    traces = tracing.get_traces(service=envoy_service, attributes={"guid:x-request-id": request_id})

    assert len(traces) == 1, f"No '{envoy_service}' trace for request_id {request_id}; span reporting was suppressed"
