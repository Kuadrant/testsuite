"""Tests for Kuadrant tracing"""

import os
from time import sleep


def test_tracing(client, auth, tracing):
    """
    Tests that traces are collected from Authorino and Limitador

    Trace IDs do not propagate to wasm modules in Istio/Envoy, affecting trace continuity in Limitador:
    https://github.com/envoyproxy/envoy/issues/22028
    That is the reason why we set parent trace ID in request.
    """
    trace_id = os.urandom(16).hex()
    client.get("/get", auth=auth, headers={"Traceparent": f"00-{trace_id}-{os.urandom(8).hex()}-01"})
    sleep(5)  # Waits for tracing backend to collect all traces

    trace = tracing.get_trace(trace_id)
    assert len(trace) == 1, f"No trace was found in tracing backend with trace_id: {trace_id}"
    service_names = [process["serviceName"] for process in trace[0]["processes"].values()]
    assert "authorino" in service_names
    assert "limitador" in service_names
