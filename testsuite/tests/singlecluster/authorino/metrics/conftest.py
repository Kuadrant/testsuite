"""Conftest for the Authorino metrics tests"""

import pytest

from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor


@pytest.fixture(scope="package")
def service_monitor(cluster, request, blame, authorino):
    """Create ServiceMonitor object to follow Authorino /metrics and /server-metrics endpoints"""
    label = {"app": authorino.name() + "metrics"}
    authorino.metrics_service.label(label)
    endpoints = [MetricsEndpoint("/metrics", "http"), MetricsEndpoint("/server-metrics", "http")]
    monitor = ServiceMonitor.create_instance(
        cluster.change_project(authorino.namespace()), blame("sm"), endpoints, match_labels=label
    )
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="package", autouse=True)
def wait_for_active_targets(prometheus, service_monitor):
    """Waits for all endpoints in Service Monitor to become active targets"""
    assert prometheus.is_reconciled(service_monitor), "Service Monitor didn't get reconciled in time"
