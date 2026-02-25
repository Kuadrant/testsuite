"""Tests for Kuadrant policy metrics lifecycle (increment/decrement on policy create/delete)."""

import backoff
import pytest

from testsuite.config import settings
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.observability, pytest.mark.disruptive]

POLICY_METRICS = ["kuadrant_policies_total", "kuadrant_policies_enforced"]


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


def test_metric_policy_lifecycle(prometheus, cluster, blame, route, module_label):
    """Tests that policy metrics increment on create and decrement on delete"""
    initial_counts = {m: _get_metric_value(prometheus, m, "RateLimitPolicy") for m in POLICY_METRICS}

    policy = RateLimitPolicy.create_instance(cluster, blame("rlp-lc"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    policy.commit()
    policy.wait_for_ready()

    for metric in POLICY_METRICS:

        @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=12)
        def _wait_for_increment(m=metric):
            return _get_metric_value(prometheus, m, "RateLimitPolicy") > initial_counts[m]

        assert _wait_for_increment(), (
            f"Expected '{metric}' for RateLimitPolicy to increment from {initial_counts[metric]}, "
            f"but got: {_get_metric_value(prometheus, metric, 'RateLimitPolicy')}"
        )

    counts_before_delete = {m: _get_metric_value(prometheus, m, "RateLimitPolicy") for m in POLICY_METRICS}
    policy.delete()

    for metric in POLICY_METRICS:

        @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=12)
        def _wait_for_decrement(m=metric):
            return _get_metric_value(prometheus, m, "RateLimitPolicy") < counts_before_delete[m]

        assert _wait_for_decrement(), (
            f"Expected '{metric}' for RateLimitPolicy to decrement from {counts_before_delete[metric]}, "
            f"but got: {_get_metric_value(prometheus, metric, 'RateLimitPolicy')}"
        )
