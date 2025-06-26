"""
Tests the enabling and disabling of observability configuration via the Kuadrant CR
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]

SERVICE_MONITOR_METRICS = [
    "controller_runtime_reconcile_total",
    "controller_runtime_reconcile_errors_total",
    "controller_runtime_max_concurrent_reconciles",
    "workqueue_adds_total",
    "workqueue_depth",
]

POD_MONITOR_METRICS = [
    "istio_requests_total",
    "istio_response_bytes_count",
    "istio_response_bytes_sum",
    "istio_agent_cert_expiry_seconds",
    "istio_agent_outgoing_latency",
]


@pytest.fixture(scope="module")
def service_monitor_metrics(service_monitors, prometheus):
    """Return metrics from ServiceMonitors"""
    for sm in service_monitors:
        assert prometheus.is_reconciled(sm), f"{sm.name()} not reconciled in Prometheus"
        prometheus.wait_for_scrape(sm, "/metrics")

    # Only collect required metrics
    results = {}
    for metric in SERVICE_MONITOR_METRICS:
        data = prometheus.get_metrics(metric)
        if data:
            results[metric] = data.names
    return results


@pytest.fixture(scope="module")
def pod_monitor_metrics(client, pod_monitors, prometheus):
    """Return metrics from PodMonitors"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    for pm in pod_monitors:
        assert prometheus.is_reconciled(pm), f"{pm.name()} not reconciled in Prometheus"
        prometheus.wait_for_scrape(pm, "/stats/prometheus")

    results = {}
    for metric in POD_MONITOR_METRICS:
        data = prometheus.get_metrics(metric)
        if data:
            results[metric] = data.names
    return results


@pytest.mark.parametrize("metric", SERVICE_MONITOR_METRICS)
def test_service_monitor_metrics(metric, service_monitor_metrics):
    """Check ServiceMonitor metrics are present"""
    assert metric in service_monitor_metrics


@pytest.mark.parametrize("metric", POD_MONITOR_METRICS)
def test_pod_monitor_metrics(metric, pod_monitor_metrics, prometheus):
    """Check PodMonitor metrics are present and match expected values if predictable"""
    assert metric in pod_monitor_metrics

    # Both source and destination proxies emit metrics for each request, so 5 requests result in 10 metric entries total
    predictable_metrics = {
        "istio_requests_total": 10,
        "istio_response_bytes_count": 10,
    }

    if metric in predictable_metrics:
        result = prometheus.get_metrics(metric)
        total = sum(result.values) if result and result.values else 0
        assert (
            total == predictable_metrics[metric]
        ), f"{metric} expected to be {predictable_metrics[metric]}, got {total}"
