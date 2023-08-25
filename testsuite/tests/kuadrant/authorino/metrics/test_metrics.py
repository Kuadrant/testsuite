"""Tests for integrity of the metrics endpoints"""
import pytest


METRICS = [
    "controller_runtime_reconcile_total",
    "controller_runtime_reconcile_errors_total",
    "controller_runtime_max_concurrent_reconciles",
    "workqueue_adds_total",
    "workqueue_depth",
    "workqueue_longest_running_processor_seconds",
    "workqueue_retries_total",
    "workqueue_unfinished_work_seconds",
    "rest_client_requests_total",
]

METRICS_HISTOGRAM = [
    "controller_runtime_reconcile_time_seconds",
    "workqueue_queue_duration_seconds",
    "workqueue_work_duration_seconds",
]

SERVER_METRICS = [
    "auth_server_authconfig_total",
    "auth_server_authconfig_response_status",
    "auth_server_response_status",
    "grpc_server_handled_total",
    "grpc_server_msg_received_total",
    "grpc_server_msg_sent_total",
    "grpc_server_started_total",
]

SERVER_METRICS_HISTOGRAM = [
    "auth_server_authconfig_duration_seconds",
    "grpc_server_handling_seconds",
]


@pytest.fixture(scope="module")
def metrics_keys(authorino, prometheus):
    """Return all metrics defined for the Authorino metrics service"""
    prometheus.wait_for_scrape(authorino.metrics_service.name(), "/metrics")
    prometheus.wait_for_scrape(authorino.metrics_service.name(), "/server-metrics")

    return prometheus.get_metrics(labels={"service": authorino.metrics_service.name()}).names


@pytest.mark.parametrize("metric", METRICS)
def test_metrics(metric, metrics_keys):
    """Test for metrics that Authorino export at the /metrics endpoint"""
    assert metric in metrics_keys


@pytest.mark.parametrize("metric", METRICS_HISTOGRAM)
def test_metrics_histogram(metric, metrics_keys):
    """Test for histogram metrics that Authorino export at the /metrics endpoint"""
    for suffix in ["_bucket", "_sum", "_count"]:
        assert metric + suffix in metrics_keys


@pytest.mark.parametrize("metric", SERVER_METRICS)
def test_server_metrics(metric, metrics_keys):
    """Test for metrics that Authorino export at the /server-metrics endpoint"""
    assert metric in metrics_keys


@pytest.mark.parametrize("metric", SERVER_METRICS_HISTOGRAM)
def test_server_metrics_histogram(metric, metrics_keys):
    """Test for histogram metrics that Authorino export at the /server-metrics endpoint"""
    for suffix in ["_bucket", "_sum", "_count"]:
        assert metric + suffix in metrics_keys
