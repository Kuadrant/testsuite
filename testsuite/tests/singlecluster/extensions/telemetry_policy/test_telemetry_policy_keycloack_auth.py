"""
Test that custom labels defined in TelemetryPolicy are correctly added to Limitador metrics.

This test variant uses Keycloak/OIDC authentication where user/group labels are sourced from
OIDC token claims and user attributes.
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.prometheus import has_label


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.extensions]


@pytest.fixture(scope="module")
def realm_with_attributes(keycloak):
    """Ensure the realm allows a custom user attribute and configure client mapper."""
    keycloak.realm.add_user_attributes("group", "Group")
    keycloak.client.add_user_attribute_mapper("group", "group")


@pytest.fixture(scope="module")
def user(request, keycloak, realm_with_attributes, blame):  # pylint: disable=unused-argument
    """Creates new user with specified group"""
    return keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"group": ["testgroup"]})


@pytest.fixture(scope="module")
def auth(user, keycloak):  # pylint: disable=unused-argument
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add Keycloak identity to AuthConfig"""
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
def test_labels_telemtry_policy_limitador_metrics(limitador_metrics, route, metric, expected_value, user):
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
    assert user_value == user.properties["username"]

    group_value = metrics.metrics[0]["metric"]["group"]
    assert group_value == user.properties["attributes"]["group"][0]

    # Check if picked metric has correct value
    metric_value = metrics.values[0]
    assert metric_value == expected_value
