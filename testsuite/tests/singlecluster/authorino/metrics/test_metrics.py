"""Tests for integrity of the metrics endpoints"""

import backoff
import pytest

pytestmark = [pytest.mark.observability, pytest.mark.authorino]

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
def metrics_labels(authorino, service_monitor, prometheus, client, auth):
    """Send a request to generate metrics and return Prometheus query labels"""
    prometheus.wait_for_scrape(service_monitor, "/metrics")
    prometheus.wait_for_scrape(service_monitor, "/server-metrics")

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    return {"service": authorino.metrics_service.name()}


@pytest.fixture(scope="module")
def metrics_keys(prometheus, metrics_labels):
    """Return a function that checks if a metric exists, retrying for propagation delays"""

    @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=6)
    def _has_metric(metric):
        return metric in prometheus.get_metrics(labels=metrics_labels).names

    return _has_metric


@pytest.mark.parametrize("metric", METRICS)
def test_metrics(metric, metrics_keys):
    """Test for metrics that Authorino export at the /metrics endpoint"""
    assert metrics_keys(metric), f"Metric '{metric}' not found"


@pytest.mark.parametrize("metric", METRICS_HISTOGRAM)
def test_metrics_histogram(metric, metrics_keys):
    """Test for histogram metrics that Authorino export at the /metrics endpoint"""
    for suffix in ["_bucket", "_sum", "_count"]:
        assert metrics_keys(metric + suffix), f"Metric '{metric + suffix}' not found"


@pytest.mark.parametrize("metric", SERVER_METRICS)
def test_server_metrics(metric, metrics_keys):
    """Test for metrics that Authorino export at the /server-metrics endpoint"""
    assert metrics_keys(metric), f"Metric '{metric}' not found"


@pytest.mark.parametrize("metric", SERVER_METRICS_HISTOGRAM)
def test_server_metrics_histogram(metric, metrics_keys):
    """Test for histogram metrics that Authorino export at the /server-metrics endpoint"""
    for suffix in ["_bucket", "_sum", "_count"]:
        assert metrics_keys(metric + suffix), f"Metric '{metric + suffix}' not found"
