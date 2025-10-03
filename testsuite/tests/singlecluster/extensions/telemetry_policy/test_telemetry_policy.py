import pytest


@pytest.fixture(scope="module", autouse=True)
def scrape_metrics_created_by_requests(prometheus, pod_monitor, client):
    """
    Creates 5 requests, from which 3 are authorized and 2 are rate limited.
    Waits until Prometheus scrapes '/metrics' endpoint.
    """
    client.get_many("/get", 5)
    prometheus.wait_for_scrape(pod_monitor, "/metrics")


@pytest.mark.parametrize("metric, expected_value", [("authorized_calls", 3), ("authorized_hits", 3), ("limited_calls", 2)])
def test_calls_metric(prometheus, limitador, route, metric, expected_value, pod_monitor):
    """Tests that `authorized_calls` and `limited_calls` are emitted and correctly incremented"""
    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
            "path": "/get",
        }
    )

    authorized = metrics.filter(lambda x: x["metric"]["__name__"] == metric)
    assert len(authorized.metrics) == 1
    assert authorized.values[0] == expected_value
