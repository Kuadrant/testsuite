"""Tests the enabling of observability configuration via the Kuadrant CR"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]

SERVICE_MONITOR_METRICS = [
    "controller_runtime_active_workers",
    "controller_runtime_reconcile_total",
    "controller_runtime_reconcile_errors_total",
    "workqueue_work_duration_seconds_bucket",
    "workqueue_work_duration_seconds_count",
    "workqueue_queue_duration_seconds_bucket",
    "workqueue_queue_duration_seconds_count",
    "workqueue_retries_total",
    "workqueue_unfinished_work_seconds",
    "workqueue_adds_total",
    "workqueue_depth",
    "workqueue_longest_running_processor_seconds",
]

POD_MONITOR_METRICS = [
    "istio_requests_total",
    "istio_response_bytes_count",
    "istio_response_bytes_sum",
    "istio_agent_cert_expiry_seconds",
    "istio_agent_outgoing_latency",
    "istio_agent_num_outgoing_requests",
    "istio_agent_process_resident_memory_bytes",
    "istio_agent_process_cpu_seconds_total",
    "istio_agent_scrapes_total",
    "istio_agent_startup_duration_seconds",
]

PREDICTABLE_METRICS = [
    "istio_requests_total",
    "istio_response_bytes_count",
]


@pytest.mark.parametrize("metric", SERVICE_MONITOR_METRICS)
def test_service_monitor_metrics_per_service(metric, service_monitor_metrics_by_service):
    """Tests that all expected metrics appear in the data collected from each ServiceMonitor"""
    for service_name, metrics in service_monitor_metrics_by_service.items():
        assert metric in metrics, f"Expected metric '{metric}' in '{service_name}'. Metrics found: {metrics}"


@pytest.mark.parametrize("metric", POD_MONITOR_METRICS)
def test_pod_monitor_metrics(metric, pod_monitor_metrics):
    """Tests that each expected PodMonitor metric is present"""
    assert metric in pod_monitor_metrics.names


@pytest.mark.parametrize("metric", PREDICTABLE_METRICS)
def test_pod_monitor_metrics_values(metric, pod_monitor_metrics):
    """Tests that PodMonitor metrics have expected source entries"""
    filtered_metrics = pod_monitor_metrics.filter(lambda x: x["metric"]["__name__"] == metric)

    source_metrics = filtered_metrics.filter(lambda x: x["metric"].get("reporter") == "source")

    assert len(source_metrics.values) == 2, f"{metric} expected 2 source metrics, got {len(source_metrics.values)}"

    # Each metric entry should have value of 1
    for i, value in enumerate(source_metrics.values):
        assert value == 1, f"{metric} source metric {i} expected value 1, got {value}"
