"""
Tests for TokenRateLimitPolicy metrics with TelemetryPolicy

User Guide:
https://github.com/Kuadrant/kuadrant-operator/blob/a1ad64a2fb9230985230b57695fface04c3b8d3c/doc/user-guides/observability/token-metrics.md
"""

import pytest

from .conftest import MODEL_NAME, USERS

pytestmark = [pytest.mark.observability, pytest.mark.limitador]


basic_request = {
    "model": MODEL_NAME,
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": False,  # disable streaming (default)
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "max_tokens": 50,
}


@pytest.fixture(scope="module")
def token_usage(prometheus, pod_monitor, client, user_data):
    """Send requests to generate metrics, trigger rate limiting and return token usage"""
    usage_data = {}

    for user_type, user_info in user_data.items():
        tokens = 0
        for _ in range(10):
            response = client.post("/v1/chat/completions", auth=user_info["auth"], json={**basic_request})
            if response.status_code == 200:
                tokens += response.json().get("usage", {}).get("total_tokens", 0)
            elif response.status_code == 429:
                break  # stop once user is rate-limited

        usage_data[f"{user_type}_total_tokens"] = tokens

    # Wait for metrics to propagate
    prometheus.wait_for_scrape(pod_monitor, "/metrics")

    return usage_data


@pytest.mark.parametrize("user_type", USERS)
def test_authorized_hits_metric_exists_and_increments(
    prometheus, limitador, route, pod_monitor, user_data, token_usage, user_type
):
    """Verify `authorized_hits` metric is emitted, reported and accumulates tokens consumed for users/groups/models"""
    user_info = user_data[user_type]

    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
            "user": user_info["user_id"],
            "group": user_info["group"],
            "model": MODEL_NAME,
        }
    )

    # Ensure `authorized_hits` metric exists for this user/group
    authorized_hits = metrics.filter(lambda x: x["metric"]["__name__"] == "authorized_hits")
    assert len(authorized_hits.metrics) == 1

    # Verify the metric is accumulating tokens
    actual_hits = authorized_hits.values[0]
    expected_tokens = token_usage[f"{user_type}_total_tokens"]
    assert actual_hits > 0, f"authorized_hits must be > 0, got {actual_hits}"

    # Verify the token metric value remains within the range of total tokens consumed
    # Token values will vary slightly due to timing of Prometheus scrapes, hence why exact matching is not asserted
    assert (
        actual_hits <= expected_tokens
    ), f"authorized_hits ({actual_hits}) should not exceed tokens consumed ({expected_tokens}) for {user_type} user"


@pytest.mark.parametrize("user_type", USERS)
def test_metrics_reported_per_user_and_group(
    prometheus, limitador, route, pod_monitor, user_data, token_usage, user_type
):  # pylint: disable=unused-argument
    """Ensure 'authorized_calls', and 'limited_calls' are reported for user/group"""
    user_info = user_data[user_type]

    metrics = prometheus.get_metrics(
        labels={
            "pod": limitador.pod.name(),
            "limitador_namespace": f"{route.namespace()}/{route.name()}",
            "job": f"{pod_monitor.namespace()}/{pod_monitor.name()}",
        }
    )

    for metric_name in ("authorized_calls", "limited_calls"):
        user_metrics = metrics.filter(
            lambda x, mn=metric_name, group=user_info["group"], user_id=user_info["user_id"]: (
                x["metric"]["__name__"] == mn and x["metric"]["group"] == group and x["metric"]["user"] == user_id
            )
        )
        assert len(user_metrics.metrics) == 1, f"{metric_name} metric not found with {user_type} user/group labels"
