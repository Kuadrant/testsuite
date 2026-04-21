"""Tests for Kuadrant policy metrics lifecycle (increment/decrement on policy create/delete)."""

import pytest

from testsuite.config import settings
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.observability, pytest.mark.disruptive]

POLICY_METRICS = ["kuadrant_policies_total", "kuadrant_policies_enforced"]


def _metric_labels(metric, policy_kind):
    """Return Prometheus query labels for a given metric and policy kind"""
    labels = {
        "service": "kuadrant-operator-metrics",
        "kind": policy_kind,
        "namespace": settings["service_protection"]["system_project"],
    }
    if metric == "kuadrant_policies_enforced":
        labels["status"] = "true"
    return labels


def _get_metric_value(prometheus, metric, policy_kind):
    """Helper to get current metric value for a given policy kind"""
    metrics = prometheus.get_metrics(key=metric, labels=_metric_labels(metric, policy_kind))
    return metrics.values[0] if metrics.values else 0


@pytest.mark.flaky(reruns=0)
def test_metric_policy_lifecycle(request, prometheus, cluster, blame, route, module_label):
    """Tests that policy metrics increment on create and decrement on delete"""
    initial_counts = {m: _get_metric_value(prometheus, m, "RateLimitPolicy") for m in POLICY_METRICS}

    policy = RateLimitPolicy.create_instance(cluster, blame("rlp-lc"), route, labels={"testRun": module_label})
    request.addfinalizer(policy.delete)
    policy.add_limit("basic", [Limit(5, "10s")])
    policy.commit()
    policy.wait_for_ready()

    for metric in POLICY_METRICS:
        assert prometheus.wait_for_metric(
            metric,
            initial_counts[metric] + 1,
            labels=_metric_labels(metric, "RateLimitPolicy"),
        ), (
            f"Expected '{metric}' to be {initial_counts[metric] + 1} on policy creation,"
            f" got {_get_metric_value(prometheus, metric, 'RateLimitPolicy')}"
        )

    policy.delete()

    for metric in POLICY_METRICS:
        assert prometheus.wait_for_metric(
            metric,
            initial_counts[metric],
            labels=_metric_labels(metric, "RateLimitPolicy"),
        ), (
            f"Expected '{metric}' to be {initial_counts[metric]} on policy deletion,"
            f" got {_get_metric_value(prometheus, metric, 'RateLimitPolicy')}"
        )
