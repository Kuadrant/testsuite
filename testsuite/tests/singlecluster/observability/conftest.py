"""Conftest for observability tests"""

import backoff
import pytest
from openshift_client import selector

from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor


@pytest.fixture(scope="module")
def commit():
    """Override the commit fixture to do nothing"""
    return None


@pytest.fixture(scope="module", autouse=True)
def no_observability_metrics_before_enable(prometheus):
    """Verify no Kuadrant-related observability targets are active before enabling observability"""

    @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
    def targets_cleared():
        targets = prometheus.get_active_targets()
        return all("kuadrant" not in t.get("labels", {}).get("job", "") for t in targets)

    if not targets_cleared():
        raise AssertionError("Observability targets still present in Prometheus before enabling observability")


@pytest.fixture(scope="module")
def enable_observability(kuadrant, request):
    """Enable observability"""
    kuadrant.set_observability(True)

    def _reset():
        kuadrant.set_observability(False)

    request.addfinalizer(_reset)


@pytest.fixture(scope="module")
def service_monitors(enable_observability, cluster, testconfig):  # pylint: disable=unused-argument
    """Return all 4 expected ServiceMonitors created by enabling observability"""
    expected_count = 4

    service = cluster.change_project(testconfig["service_protection"]["system_project"])
    with service.context:
        monitors = selector("servicemonitor", labels={"kuadrant.io/observability": "true"}).objects(cls=ServiceMonitor)

        if len(monitors) != expected_count:
            raise AssertionError(f"Expected {expected_count} ServiceMonitors, got {len(monitors)}")

        return monitors


@pytest.fixture(scope="module")
def pod_monitors(enable_observability, cluster, testconfig):  # pylint: disable=unused-argument
    """Return PodMonitor created by enabling observability"""

    pod = cluster.change_project(testconfig["service_protection"]["project"])
    with pod.context:
        monitors = selector("podmonitor", labels={"kuadrant.io/observability": "true"}).objects(cls=PodMonitor)

        if len(monitors) < 1:
            raise AssertionError("Expected at least 1 PodMonitor, but found none")

        return monitors
