"""Tests for Kuadrant policy metrics lifecycle (increment/decrement on policy create/delete)."""

import pytest

from testsuite.config import settings
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.observability, pytest.mark.disruptive]

POLICY_METRICS = ["kuadrant_policies_total", "kuadrant_policies_enforced"]


@pytest.fixture(scope="module")
def service_monitor(service_monitors):
    """Return the kuadrant-operator ServiceMonitor"""
    return next(sm for sm in service_monitors if "kuadrant-operator-monitor" in sm.name())


def _get_metric_value(prometheus, metric, kind):
    """Helper to get current metric value for a given policy kind"""
    labels = {
        "service": "kuadrant-operator-metrics",
        "kind": kind,
        "namespace": settings["service_protection"]["system_project"],
    }
    if metric == "kuadrant_policies_enforced":
        labels["status"] = "true"

    metrics = prometheus.get_metrics(key=metric, labels=labels)
    return metrics.values[0] if metrics.values else 0


def test_metric_policy_lifecycle(prometheus, cluster, blame, route, module_label, service_monitor):
    """Tests that policy metrics increment on create and decrement on delete"""
    initial_counts = {m: _get_metric_value(prometheus, m, "RateLimitPolicy") for m in POLICY_METRICS}

    policy = RateLimitPolicy.create_instance(cluster, blame("rlp-lc"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    policy.commit()
    policy.wait_for_ready()

    prometheus.wait_for_scrape(service_monitor, "/metrics")

    for metric in POLICY_METRICS:
        current_count = _get_metric_value(prometheus, metric, "RateLimitPolicy")
        assert (
            current_count == initial_counts[metric] + 1
        ), f"Expected '{metric}' to be {initial_counts[metric] + 1}, got {current_count}"

    policy.delete()
    prometheus.wait_for_scrape(service_monitor, "/metrics")

    for metric in POLICY_METRICS:
        current_count = _get_metric_value(prometheus, metric, "RateLimitPolicy")
        assert (
            current_count == initial_counts[metric]
        ), f"Expected '{metric}' to be {initial_counts[metric]}, got {current_count}"
