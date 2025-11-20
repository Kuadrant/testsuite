"""
Test that custom labels defined in TelemetryPolicy are correctly added to Limitador metrics.

This test variant uses API Key authentication where user/group labels are sourced from
API key annotations.
"""

import pytest

from testsuite.prometheus import has_label
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom


pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.extensions]


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    annotations = {"user": "testuser", "group": "testgroup"}
    return create_api_key("api-key", module_label, "IAMTESTUSER", annotations=annotations)


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Setup AuthPolicy for test"""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "userid": ValueFrom("auth.identity.metadata.annotations.user"),
                "groupid": ValueFrom("auth.identity.metadata.annotations.group"),
            }
        ),
    )
    return authorization


@pytest.mark.parametrize(
    "metric, expected_value", [("authorized_calls", 3), ("authorized_hits", 3), ("limited_calls", 2)]
)
def test_labels_telemetry_policy_limitador_api_key(limitador_metrics, api_key, route, metric, expected_value):
    """
    Test that custom labels from TelemetryPolicy annotations are correctly propagated to Limitador metrics.
    Verifies that 'user' and 'group' labels from API key annotations appear in authorized_calls,
    authorized_hits, and limited_calls metrics with correct values.
    """

    # Pick one metric with specific route label
    metrics_on_route = limitador_metrics.filter(has_label("limitador_namespace", f"{route.namespace()}/{route.name()}"))
    filtered_metric = metrics_on_route.filter(has_label("__name__", metric))
    assert (
        len(filtered_metric.metrics) == 1
    ), f"Expected exactly 1 '{metric}' metric, but found {len(filtered_metric.metrics)}"

    # Check if labels user and group are added on the picked metric
    assert (
        "user" in filtered_metric.metrics[0]["metric"]
    ), f"Expected 'user' label in {metric} metric, but it was not found"
    assert (
        "group" in filtered_metric.metrics[0]["metric"]
    ), f"Expected 'group' label in {metric} metric, but it was not found"

    # Check if user/group label has correct name
    user_value = filtered_metric.metrics[0]["metric"]["user"]
    expected_user = api_key.model.metadata.annotations["user"]
    assert user_value == expected_user, f"Expected user label to be '{expected_user}', but got '{user_value}'"

    group_value = filtered_metric.metrics[0]["metric"]["group"]
    expected_group = api_key.model.metadata.annotations["group"]
    assert group_value == expected_group, f"Expected group label to be '{expected_group}', but got '{group_value}'"

    # Check if picked metric has correct value
    metric_value = filtered_metric.values[0]
    assert (
        metric_value == expected_value
    ), f"Expected {metric} metric value to be {expected_value}, but got {metric_value}"
