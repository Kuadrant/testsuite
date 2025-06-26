"""
Tests the enabling and disabling of observability configuration via the Kuadrant CR
"""

import time
import pytest
import backoff


@pytest.fixture(scope="module")
def generate_requests(client):
    """Send traffic to generate metrics and verify requests succeed"""

    def _send(n=10, delay=0.5):
        for _ in range(n):
            response = client.get("/get")
            assert response.status_code == 200
            if delay:
                time.sleep(delay)

    return _send


@backoff.on_predicate(backoff.constant, interval=10, max_tries=24)
def wait_for_istio_requests(prometheus):
    """Wait until istio_requests_total is observed in Prometheus"""
    query = 'sum(istio_requests_total{reporter="source"})'
    metrics = prometheus.get_metrics(query)

    if metrics and metrics.values:
        return sum(metrics.values) > 0

    return False


def test_no_metrics_when_observability_disabled(
    gateway, configure_observability, generate_requests, prometheus, reset_observability
):  # pylint: disable=unused-argument
    """Verify that no istio_requests_total metrics are collected when observability is disabled"""
    reset_observability()
    configure_observability(False)

    generate_requests(n=10, delay=0.3)
    time.sleep(30)  # allow time for Prometheus to scrape metrics

    query = 'sum(istio_requests_total{reporter="source"})'
    metrics = prometheus.get_metrics(query)

    assert (
        metrics is None or len(metrics.metrics) == 0
    ), f"istio_requests_total activity found when observability is disabled: {metrics}"


def test_istio_requests_generate_metrics(
    gateway, configure_observability, generate_requests, prometheus, wait_for_monitors, reset_observability
):  # pylint: disable=unused-argument
    """Verify istio_requests_total metrics appear when observability is enabled and traffic is generated"""
    configure_observability(True)

    assert wait_for_monitors(present=True)  # wait for monitors to be created

    generate_requests(n=120, delay=0.5)

    time.sleep(60)  # sleep longer than the scrape interval to ensure enough time for Prometheus to see the metrics

    assert wait_for_istio_requests(
        prometheus
    ), "No istio_requests_total activity found after enabling observability"  # assert Prometheus sees traffic metrics


def test_no_new_metrics_after_disabling_observability(
    gateway, configure_observability, generate_requests, prometheus, wait_for_monitors, reset_observability
):  # pylint: disable=unused-argument
    """Ensure no new istio_requests_total metrics are collected after observability is disabled after being enabled"""
    configure_observability(True)

    assert wait_for_monitors(present=True)

    generate_requests(n=120, delay=0.5)

    assert wait_for_istio_requests(prometheus), "No istio_requests_total activity found after enabling observability"

    reset_observability()  # reset / disable observability

    assert wait_for_monitors(present=False)

    # Prometheus takes some time to drop targets and expire cached metrics
    time.sleep(180)  # 3-minute buffer to allow Prometheus to stop scraping

    # Get the current total request count as a baseline
    total_query = 'sum(istio_requests_total{reporter="source"})'
    baseline_metrics = prometheus.get_metrics(total_query)
    baseline_total = sum(baseline_metrics.values) if baseline_metrics and baseline_metrics.values else 0

    generate_requests(n=10, delay=0.5)  # these requests should not be scraped by Prometheus anymore

    time.sleep(60)  # allow time to see if Prometheus scrapes new metrics

    # Get the current total again to check if it has increased
    after_metrics = prometheus.get_metrics(total_query)
    after_total = sum(after_metrics.values) if after_metrics and after_metrics.values else 0
    requests_increase = after_total - baseline_total

    print(f"{after_total} (increase: {requests_increase})")

    # Fail the test only if the increase is significant, allowing for minor scrape lag
    assert requests_increase <= 5, (
        f"Unexpected metric increase ({requests_increase}) after disabling observability. "
        "This suggests monitors may not be fully deleted or Prometheus is still scraping."
    )


@pytest.mark.parametrize("enabled", [True, False])
def test_requests_always_succeed(configure_observability, client, enabled):
    """Verify that requests to the gateway succeed regardless of observability state"""
    configure_observability(enabled)
    response = client.get("/get")
    assert response.status_code == 200, f"Request failed with observability={enabled}"
