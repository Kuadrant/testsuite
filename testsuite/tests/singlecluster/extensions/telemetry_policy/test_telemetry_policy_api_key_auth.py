"""
Test that custom labels defined in TelemetryPolicy are correctly added to Limitador metrics.

This test variant uses API Key authentication where user/group labels are sourced from
API key annotations.
"""

import pytest

from testsuite.prometheus import has_label
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.extensions]


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
def test_labels_telemtry_policy_limitador_metrics(limitador_metrics, api_key, route, metric, expected_value):
    """
    Test that custom labels from TelemetryPolicy annotations are correctly propagated to Limitador metrics.
    Verifies that 'user' and 'group' labels from API key annotations appear in authorized_calls,
    authorized_hits, and limited_calls metrics with correct values.
    """

    # Pick one metric with specific route label
    metrics_on_route = limitador_metrics.filter(has_label("limitador_namespace", f"{route.namespace()}/{route.name()}"))
    metrics = metrics_on_route.filter(has_label("__name__", metric))

    # Check if labels user and group are added on the picked metric
    assert "user" in metrics.metrics[0]["metric"] and "group" in metrics.metrics[0]["metric"]

    # Check if user/group label has correct name
    user_value = metrics.metrics[0]["metric"]["user"]
    assert user_value == api_key.model.metadata.annotations["user"]

    group_value = metrics.metrics[0]["metric"]["group"]
    assert group_value == api_key.model.metadata.annotations["group"]

    # Check if picked metric has correct value
    metric_value = metrics.values[0]
    assert metric_value == expected_value
