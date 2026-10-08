"""Tests that Kuadrant tracing reaches the egress gateway.

The tracing machinery itself - the EnvoyFilter reconciler, wasm-shim spans, Authorino and
Limitador spans - is gateway-agnostic and already covered on ingress in
testsuite/tests/singlecluster/tracing/data_plane_tracing/. These tests assert only that it
reaches an egress gateway, whose HTTPRoute has an Istio Hostname backendRef rather than a
Service, and that the documented Envoy/wasm trace split holds there.

Validates https://github.com/Kuadrant/kuadrant-operator/pull/2165
"""

import backoff
import pytest
from openshift_client import selector

from testsuite.kubernetes.envoy_filter import EnvoyFilter

pytestmark = [
    pytest.mark.kuadrant_only,
    pytest.mark.egress_gateway,
    pytest.mark.observability,
    pytest.mark.authorino,
    pytest.mark.limitador,
]


@pytest.fixture(scope="module")
def request_id(client, auth):
    """Sends one authorized request through the egress gateway and returns its x-request-id"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200, f"Expected the egress request to succeed, got {response.status_code}"
    request_id = response.headers.get("x-request-id")
    assert request_id is not None, "Gateway did not return an x-request-id header"
    return request_id


@pytest.fixture(scope="module")
def filter_trace(request_id, tracing):
    """kuadrant-filter trace for the authorized egress request.

    min_processes makes the lookup retry until all three Kuadrant services have reported;
    Authorino and Limitador spans arrive slightly after the wasm-shim's own.
    """
    traces = tracing.get_traces(service="kuadrant-filter", min_processes=3, attributes={"request_id": request_id})
    assert len(traces) == 1, f"Expected exactly one kuadrant-filter trace for request_id {request_id}"
    return traces[0]


def test_tracing_envoyfilter_created_for_egress_gateway(gateway, cluster):
    """
    Test that the tracing EnvoyFilter is provisioned for the egress gateway.

    The reconciler only creates it for gateways that sit in an effective policy path. An egress
    HTTPRoute reaches its backend through an Istio Hostname reference instead of a Service, so
    this confirms that topology still puts the gateway in that path.
    """
    expected_name = f"kuadrant-tracing-{gateway.name()}"

    @backoff.on_predicate(backoff.constant, lambda x: not x, interval=5, max_tries=12, jitter=None)
    def wait_for_envoyfilter():
        with cluster.context:
            return [
                envoy_filter
                for envoy_filter in selector("envoyfilter", labels={"kuadrant.io/tracing": "true"}).objects(
                    cls=EnvoyFilter
                )
                if envoy_filter.name() == expected_name
            ]

    envoy_filters = wait_for_envoyfilter()
    assert envoy_filters, f"No EnvoyFilter '{expected_name}' labeled kuadrant.io/tracing=true in {cluster.project}"


def test_kuadrant_spans_produced_for_egress_traffic(filter_trace):
    """
    Test that egress traffic produces the full Kuadrant span chain.

    The wasm-shim exports its own trace and propagates context to Authorino and Limitador over
    gRPC metadata, so all three services appear in a single kuadrant-filter trace.
    """
    process_services = filter_trace.get_process_services()

    for service in ["kuadrant-filter", "authorino", "limitador"]:
        assert service in process_services, f"Service '{service}' not found in trace processes: {process_services}"


@pytest.mark.user_managed_istio
def test_envoy_and_filter_traces_are_separate_but_correlated(request_id, filter_trace, tracing, module_label, cluster):
    """
    Test that the Envoy trace and the kuadrant-filter trace are distinct traces sharing an x-request-id.

    Envoy does not propagate trace context into the wasm VM
    (https://github.com/envoyproxy/envoy/issues/22028), so each request yields two unrelated
    traces correlated only by x-request-id. This pins that documented behaviour: if the ABI
    limitation is ever fixed the two trace IDs will converge and this test will fail, which is
    the signal we want.
    """
    # Istio reports the gateway under its canonical service name, which is the pod's app label
    envoy_service = f"{module_label}.{cluster.project}"
    envoy_traces = tracing.get_traces(service=envoy_service, attributes={"guid:x-request-id": request_id})
    assert len(envoy_traces) == 1, f"Expected exactly one '{envoy_service}' trace for request_id {request_id}"

    assert envoy_traces[0].trace_id != filter_trace.trace_id, (
        "Envoy and kuadrant-filter traces share a trace ID. The wasm trace-context limitation "
        "(envoyproxy/envoy#22028) may have been fixed - this assertion needs revisiting."
    )
