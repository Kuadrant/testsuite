"""
Test that custom labels defined in TelemetryPolicy are correctly added to Limitador metrics.

This test variant uses Keycloak/OIDC authentication where user/group labels are sourced from
OIDC token claims and user attributes.
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.prometheus import has_label


pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.extensions]


@pytest.fixture(scope="module")
def keycloak(keycloak):
    """
    Adds a custom attribute to the realm's user profile and configures
    the client's protocol mapper to include this attribute in OIDC tokens.
    """
    keycloak.realm.add_user_attributes("group", "Group")
    keycloak.client.add_user_attribute_mapper("group", "group")
    return keycloak


@pytest.fixture(scope="module")
def user(keycloak, blame):
    """Creates new user with specified group"""
    return keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"group": ["testgroup"]})


@pytest.fixture(scope="module")
def auth(user, keycloak):
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add Keycloak identity to AuthPolicy"""
    authorization.identity.add_oidc("keycloak", keycloak.well_known["issuer"])
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "userid": ValueFrom("auth.identity.preferred_username"),
                "groupid": ValueFrom("auth.identity.group"),
            }
        ),
    )
    return authorization


@pytest.mark.parametrize(
    "metric, expected_value", [("authorized_calls", 3), ("authorized_hits", 3), ("limited_calls", 2)]
)
def test_labels_telemetry_policy_limitador_keycloak(limitador_metrics, route, metric, expected_value, user):
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
    expected_user = user.properties["username"]
    assert user_value == expected_user, f"Expected user label to be '{expected_user}', but got '{user_value}'"

    group_value = filtered_metric.metrics[0]["metric"]["group"]
    expected_group = user.properties["attributes"]["group"][0]
    assert group_value == expected_group, f"Expected group label to be '{expected_group}', but got '{group_value}'"

    # Check if picked metric has correct value
    metric_value = filtered_metric.values[0]
    assert (
        metric_value == expected_value
    ), f"Expected {metric} metric value to be {expected_value}, but got {metric_value}"
