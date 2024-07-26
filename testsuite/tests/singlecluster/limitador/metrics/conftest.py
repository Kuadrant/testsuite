"""Conftest for limitador metrics tests"""

import pytest

from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor


@pytest.fixture(scope="module")
def pod_monitor(cluster, testconfig, request, blame, limitador):
    """Creates Pod Monitor object to watch over '/metrics' endpoint of limitador pod"""
    project = cluster.change_project(testconfig["service_protection"]["system_project"])

    endpoints = [MetricsEndpoint("/metrics", "http")]
    monitor = PodMonitor.create_instance(project, blame("pd"), endpoints, match_labels={"app": limitador.name()})
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="module", autouse=True)
def wait_for_active_targets(prometheus, pod_monitor):
    """Waits for all endpoints in Pod Monitor to become active targets"""
    assert prometheus.is_reconciled(pod_monitor)
