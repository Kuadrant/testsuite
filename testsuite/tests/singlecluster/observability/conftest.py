"""Conftest for observability tests"""

import backoff
import pytest
from openshift_client import selector

from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor


SERVICE_MONITOR_SERVICES = [
    "kuadrant-operator-metrics",
    "dns-operator-controller-manager-metrics-service",
    "limitador-operator-metrics",
    "authorino-operator-metrics",
]

POD_MONITOR_JOB = [
    "kuadrant/istio-pod-monitor",
]


@pytest.fixture(scope="module")
def commit():
    """Override the commit fixture to do nothing"""
    return None


@pytest.fixture(scope="module", autouse=True)
def enable_observability(kuadrant, request):
    """Enable / reset observability"""
    kuadrant.set_observability(True)
    kuadrant.wait_for_ready()

    def _reset():
        kuadrant.set_observability(False)

    request.addfinalizer(_reset)


@pytest.fixture(scope="module", autouse=True)
def no_observability_metrics_before_enable(prometheus):
    """Verify that no relevant observability targets are active before enabling observability"""

    @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
    def targets_cleared():
        targets = prometheus.get_active_targets()

        for t in targets:
            labels = t.get("labels", {})
            if labels.get("service") in SERVICE_MONITOR_SERVICES:
                return False
            if labels.get("job") in POD_MONITOR_JOB:
                return False

        return True

    assert targets_cleared(), "Observability targets still present in Prometheus before enabling observability"


@pytest.fixture(scope="module")
def service_monitors(enable_observability, cluster, testconfig):  # pylint: disable=unused-argument
    """Return all 4 expected ServiceMonitors created by enabling observability"""
    context = cluster.change_project(testconfig["service_protection"]["system_project"]).context

    @backoff.on_predicate(backoff.constant, lambda x: len(x) == 4, interval=5, max_tries=12, jitter=None)
    def wait_for_monitors():
        return selector("ServiceMonitor", labels={"kuadrant.io/observability": "true"}, static_context=context).objects(
            cls=ServiceMonitor
        )

    all_monitors = wait_for_monitors()
    assert all_monitors, "Expected ServiceMonitors were not found"

    return all_monitors


@pytest.fixture(scope="module")
def pod_monitor(enable_observability, cluster):  # pylint: disable=unused-argument
    """Return PodMonitor created by enabling observability"""

    @backoff.on_predicate(backoff.constant, lambda x: len(x) == 1, interval=5, max_tries=12, jitter=None)
    def wait_for_monitor():
        return selector(
            "PodMonitor", labels={"kuadrant.io/observability": "true"}, static_context=cluster.context
        ).objects(cls=PodMonitor)

    monitor = wait_for_monitor()
    assert monitor, "PodMonitor 'istio-pod-monitor' not found"

    return monitor[0]


@pytest.fixture(scope="module")
def service_monitor_metrics_by_service(service_monitors, prometheus):
    """Return a dictionary, for each expected service, showing which metrics were collected"""
    metrics_by_service = {}

    for sm in service_monitors:
        assert prometheus.is_reconciled(sm), f"{sm.name()} not reconciled in Prometheus"
        prometheus.wait_for_scrape(sm, "/metrics")

    for service_name in SERVICE_MONITOR_SERVICES:
        metrics = prometheus.get_metrics(labels={"service": service_name})
        metrics_by_service[service_name] = set(metrics.names) if metrics and metrics.names else set()

    return metrics_by_service


@pytest.fixture(scope="module")
def pod_monitor_metrics(client, pod_monitor, prometheus):
    """Return metrics from PodMonitor"""
    result = client.get("/get")  # Trigger request traffic to generate istio metrics
    assert result.status_code == 200

    assert prometheus.is_reconciled(pod_monitor), f"{pod_monitor.name()} not reconciled in Prometheus"
    prometheus.wait_for_scrape(pod_monitor, "/stats/prometheus")

    metrics = prometheus.get_metrics(labels={"job": POD_MONITOR_JOB[0]})
    return set(metrics.names) if metrics and metrics.names else set()
