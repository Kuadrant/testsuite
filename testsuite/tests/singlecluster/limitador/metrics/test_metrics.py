"""Tests for Limitador metrics"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("multiple", [Limit(3, "10s")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def scrape_metrics_created_by_requests(prometheus, pod_monitor, client):
    """
    Creates 5 requests, from which 3 are authorized and 2 are rate limited.
    Waits until Prometheus scrapes '/metrics' endpoint.
    """
    client.get_many("/get", 5)
    prometheus.wait_for_scrape(pod_monitor, "/metrics")


@pytest.mark.parametrize("metric, expected_value", [("authorized_calls", 3), ("limited_calls", 2)])
def test_calls_metric(prometheus, limitador, rate_limit, metric, expected_value, pod_monitor):
    """Tests that `authorized_calls` and `limited_calls` are emitted and correctly incremented"""
    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{rate_limit.namespace()}/{rate_limit.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
        }
    )

    authorized = metrics.filter(lambda x: x["metric"]["__name__"] == metric)
    assert len(authorized.metrics) == 1
    assert authorized.values[0] == expected_value


def test_limitador_status_metric(prometheus, limitador, pod_monitor):
    """Tests that `limitador_up` metric is emitted"""
    # We have to use `PodMonitor` here. If `ServiceMonitor` is used, `job` label contains limitador service name,
    # therefore it is not possible to test, if the metric was created by this test (by this monitor)
    metrics = prometheus.get_metrics(
        labels={"pod": limitador.pod.name(), "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}"}
    )

    limitador_up = metrics.filter(lambda x: x["metric"]["__name__"] == "limitador_up")
    assert len(limitador_up.metrics) == 1
    assert limitador_up.values[0] == 1
