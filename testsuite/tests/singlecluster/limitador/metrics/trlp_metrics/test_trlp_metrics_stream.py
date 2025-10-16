"""
Tests for TokenRateLimitPolicy metrics with TelemetryPolicy with streaming enabled
"""

import json

import pytest

from .conftest import MODEL_NAME, USERS

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

streaming_request = {
    "model": MODEL_NAME,
    "messages": [{"role": "user", "content": "What is Kubernetes?"}],
    "stream": True,
    "usage": True,
    "stream_options": {"include_usage": True},
    "max_tokens": 50,
}


def parse_streaming_usage(response):
    """Parse the streaming response and return the `usage` object from the last JSON chunk"""
    raw = response.text.strip().splitlines()
    json_lines = [line.removeprefix("data: ").strip() for line in raw if line.startswith("data: {")]
    assert json_lines, f"No JSON chunks found in streaming response:\n{response.text}"
    last_json = json.loads(json_lines[-1])
    usage = last_json.get("usage")
    assert usage and all(
        k in usage for k in ("total_tokens", "prompt_tokens", "completion_tokens")
    ), f"Missing or invalid usage in streaming response: {last_json}"
    return usage


def extract_usage_tokens(response):
    """Return usage.total_tokens from streaming response"""
    usage = parse_streaming_usage(response)
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    return usage["total_tokens"]


@pytest.fixture(scope="module")
def token_usage(prometheus, pod_monitor, client, user_data):
    """Send streaming requests to generate metrics, trigger rate limiting and return token usage"""
    usage_data = {}

    for user_type, user_info in user_data.items():
        tokens = 0
        for _ in range(10):
            response = client.post("/v1/chat/completions", auth=user_info["auth"], json={**streaming_request})
            if response.status_code == 200:
                tokens += extract_usage_tokens(response)
            elif response.status_code == 429:
                break  # stop once user is rate-limited

        usage_data[f"{user_type}_total_tokens"] = tokens

    # Wait for metrics to propagate
    prometheus.wait_for_scrape(pod_monitor, "/metrics")

    return usage_data


@pytest.mark.parametrize("user_type", USERS)
def test_authorized_hits_metric_exists_and_increments_streaming(
    prometheus, limitador, route, pod_monitor, user_data, token_usage, user_type
):
    """Verify `authorized_hits` is emitted and accumulates tokens consumed for users/groups/models with streaming"""
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

    authorized_hits = metrics.filter(lambda x: x["metric"]["__name__"] == "authorized_hits")
    assert len(authorized_hits.metrics) == 1

    actual_hits = authorized_hits.values[0]
    expected_tokens = token_usage[f"{user_type}_total_tokens"]
    assert actual_hits > 0, f"authorized_hits must be > 0, got {actual_hits}"

    assert (
        actual_hits <= expected_tokens
    ), f"authorized_hits ({actual_hits}) should not exceed tokens consumed ({expected_tokens}) for {user_type} user"


@pytest.mark.parametrize("user_type", USERS)
def test_metrics_reported_per_user_and_group_streaming(
    prometheus, limitador, route, pod_monitor, user_data, token_usage, user_type
):  # pylint: disable=unused-argument
    """Ensure 'authorized_calls', and 'limited_calls' are reported for user/group with streaming"""
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
