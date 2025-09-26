"""
Tests for TokenRateLimitPolicy metrics with TelemetryPolicy

User Guide:
https://github.com/Kuadrant/kuadrant-operator/blob/a1ad64a2fb9230985230b57695fface04c3b8d3c/doc/user-guides/observability/token-metrics.md
"""

import pytest


basic_request = {
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # disable streaming (default)
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 50,
}


@pytest.fixture(scope="module")
def token_usage(prometheus, pod_monitor, client, free_user_auth, paid_user_auth):
    """Send requests to generate metrics, trigger rate limiting and return token usage"""
    # Free user requests
    free_tokens = 0
    for _ in range(10):
        response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request})
        if response.status_code == 200:
            free_tokens += response.json().get("usage", {}).get("total_tokens", 0)
        elif response.status_code == 429:
            break  # stop once free user is rate-limited

    # Paid user requests
    paid_tokens = 0
    for _ in range(10):
        response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request})
        if response.status_code == 200:
            paid_tokens += response.json().get("usage", {}).get("total_tokens", 0)
        elif response.status_code == 429:
            break  # stop once paid user is rate-limited

    # Wait for metrics to propagate
    prometheus.wait_for_scrape(pod_monitor, "/metrics")

    return {
        "free_total_tokens": free_tokens,
        "paid_total_tokens": paid_tokens,
    }


def test_authorized_hits_metric_exists_and_increments_free_user(
    prometheus, limitador, route, pod_monitor, free_user_api_key, token_usage
):
    """Verify `authorized_hits` metric is emitted and accumulates tokens consumed for free user/group"""
    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
            "user": free_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"],
            "group": "free",
        }
    )

    # Ensure `authorized_hits` metric exists for this user/group
    authorized_hits = metrics.filter(lambda x: x["metric"]["__name__"] == "authorized_hits")
    assert len(authorized_hits.metrics) == 1

    # Verify the metric is accumulating tokens
    actual_hits = authorized_hits.values[0]
    expected_tokens = token_usage["free_total_tokens"]
    assert actual_hits > 0, f"authorized_hits must be > 0, got {actual_hits}"

    # Verify the token metric value remains within the range of total tokens consumed
    # Token values will vary slightly due to timing of Prometheus scrapes, hence why exact matching is not asserted
    assert (
        actual_hits <= expected_tokens
    ), f"authorized_hits ({actual_hits}) should not exceed tokens consumed ({expected_tokens}) for free user"


def test_authorized_hits_metric_exists_and_increments_paid_user(
    prometheus, limitador, route, pod_monitor, paid_user_api_key, token_usage
):
    """Verify `authorized_hits` metric is emitted and accumulates tokens consumed for paid user/group"""
    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
            "user": paid_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"],
            "group": "paid",
        }
    )

    authorized_hits = metrics.filter(lambda x: x["metric"]["__name__"] == "authorized_hits")
    assert len(authorized_hits.metrics) == 1

    actual_hits = authorized_hits.values[0]
    expected_tokens = token_usage["paid_total_tokens"]
    assert actual_hits > 0, f"authorized_hits must be > 0, got {actual_hits}"
    assert (
        actual_hits <= expected_tokens
    ), f"authorized_hits ({actual_hits}) should not exceed tokens consumed ({expected_tokens}) for paid user"


def test_metrics_reported_per_user_and_group(
    prometheus, limitador, route, pod_monitor, free_user_api_key, paid_user_api_key, token_usage
):  # pylint: disable=unused-argument
    """Ensure 'authorized_hits', 'authorized_calls', and 'limited_calls' are reported separately per user/group"""
    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
        }
    )

    for metric_name in ("authorized_hits", "authorized_calls", "limited_calls"):
        free_metrics = metrics.filter(
            lambda x, mn=metric_name: x["metric"]["__name__"] == mn
            and x["metric"]["group"] == "free"
            and x["metric"]["user"] == free_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"]
        )
        paid_metrics = metrics.filter(
            lambda x, mn=metric_name: x["metric"]["__name__"] == mn
            and x["metric"]["group"] == "paid"
            and x["metric"]["user"] == paid_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"]
        )

        assert len(free_metrics.metrics) == 1, f"{metric_name} metric not found with free user/group labels"
        assert len(paid_metrics.metrics) == 1, f"{metric_name} metric not found with paid user/group labels"
