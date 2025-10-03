"""Conftest for TelemetryPolicy tests"""

from collections import Counter
import pytest

from testsuite.kuadrant.extensions.telemetry_policy import TelemetryPolicy
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor


@pytest.fixture(scope="package")
def service_monitor(cluster, request, testconfig, blame, kuadrant):
    """Create ServiceMonitor object to follow limitador-limitador service on /metrics endpoint"""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])
    endpoints = [MetricsEndpoint("/metrics", "http")]
    match_labels = {"app": kuadrant.limitador.name()}
    monitor = ServiceMonitor.create_instance(system_project, blame("sm"), endpoints, match_labels=match_labels)
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="package", autouse=True)
def wait_for_active_targets(prometheus, service_monitor):
    """Waits for all endpoints in Service Monitor to become active targets"""
    assert prometheus.is_reconciled(service_monitor), "Service Monitor didn't get reconciled in time"


@pytest.fixture(scope="module")
def telemetry_policy(cluster, blame, gateway):
    """Creates TelemetryPolicy with user and group labels"""
    telemetry_policy = TelemetryPolicy.create_instance(cluster, blame("tp"), gateway)
    telemetry_policy.add_label("user", "auth.identity.userid")
    telemetry_policy.add_label("group", "auth.identity.groupid")
    return telemetry_policy


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("testuser", [Limit(3, "10s")], when=[CelPredicate("has(auth.identity)")])
    return rate_limit


@pytest.fixture(scope="module")
def limitador_metrics(prometheus, service_monitor, client, auth):
    """
    Creates 5 requests, from which 3 are authorized and 2 are rate limited.
    Waits until Prometheus scrapes '/metrics' endpoint.
    Return all metrics from the limitador-limitador service on /metrics endpoint
    """
    responses = client.get_many("/get", 5, auth=auth)
    status_counts = Counter(r.status_code for r in responses)
    assert status_counts[200] == 3, f"Expected 3 successful responses, got {status_counts[200]}"
    assert status_counts[429] == 2, f"Expected 2 rate-limited responses, got {status_counts[429]}"

    prometheus.wait_for_scrape(service_monitor, "/metrics")
    return prometheus.get_metrics(labels={"service": "limitador-limitador"})


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, telemetry_policy, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, telemetry_policy, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
