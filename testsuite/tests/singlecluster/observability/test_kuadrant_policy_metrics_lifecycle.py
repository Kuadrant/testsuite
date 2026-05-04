"""Tests for Kuadrant policy metrics lifecycle (increment/decrement on policy create/delete)."""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.observability, pytest.mark.disruptive]

POLICY_METRICS = ["kuadrant_policies_total", "kuadrant_policies_enforced"]


def _metric_labels(metric, policy_kind, namespace):
    """Return Prometheus query labels for a given metric and policy kind"""
    labels = {
        "service": "kuadrant-operator-metrics",
        "kind": policy_kind,
        "namespace": namespace,
    }
    if metric == "kuadrant_policies_enforced":
        labels["status"] = "true"
    return labels


def _get_metric_value(prometheus, metric, policy_kind, namespace):
    """Helper to get current metric value for a given policy kind"""
    metrics = prometheus.get_metrics(key=metric, labels=_metric_labels(metric, policy_kind, namespace))
    return metrics.values[0] if metrics.values else 0


@pytest.mark.flaky(reruns=0)
def test_metric_policy_lifecycle(request, prometheus, cluster, blame, route, module_label, system_project):
    """Tests that policy metrics increment on create and decrement on delete"""
    namespace = system_project.project
    for metric in POLICY_METRICS:
        assert prometheus.wait_for_metric(metric, 0, labels=_metric_labels(metric, "RateLimitPolicy", namespace)), (
            f"Expected '{metric}' to be 0 before test,"
            f" got {_get_metric_value(prometheus, metric, 'RateLimitPolicy', namespace)}"
        )

    policy = RateLimitPolicy.create_instance(cluster, blame("rlp-lc"), route, labels={"testRun": module_label})
    request.addfinalizer(policy.delete)
    policy.add_limit("basic", [Limit(5, "10s")])
    policy.commit()
    policy.wait_for_ready()

    for metric in POLICY_METRICS:
        assert prometheus.wait_for_metric(
            metric,
            1,
            labels=_metric_labels(metric, "RateLimitPolicy", namespace),
        ), (
            f"Expected '{metric}' to be 1 on policy creation,"
            f" got {_get_metric_value(prometheus, metric, 'RateLimitPolicy', namespace)}"
        )

    policy.delete()

    for metric in POLICY_METRICS:
        assert prometheus.wait_for_metric(
            metric,
            0,
            labels=_metric_labels(metric, "RateLimitPolicy", namespace),
        ), (
            f"Expected '{metric}' to be 0 on policy deletion,"
            f" got {_get_metric_value(prometheus, metric, 'RateLimitPolicy', namespace)}"
        )
