"""
Tests that an AuthPolicy is correctly applied to a specific rule section of
an HTTPRoute, protecting only the traffic handled by that named rule.
"""

import pytest
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def route(route, backend):
    """
    Overrides the default route to have two paths: one for a protected
    service (/get) and one for a public one (/anything).
    """
    route.remove_all_rules()
    route.add_backend(backend, "/get")  # This becomes the target "rule-1"
    route.add_backend(backend, "/anything")  # This is the public rule
    return route


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, oidc_provider, route):
    """
    Creates an AuthPolicy that targets a specific rule ('rule-1') within the
    HTTPRoute.
    """
    policy = AuthPolicy.create_instance(
        cluster,
        blame("authz"),
        route,  # Target is the HTTPRoute
        section_name="rule-1",  # Target the specific named rule
        labels={"testRun": module_label},
    )
    policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    return policy


def test_authpolicy_section_name_targeting_http_route_rule(client, auth):
    """
    Tests that an AuthPolicy attached to a specific HTTPRoute rule protects
    only the requests handled by that rule.
    """
    # The '/anything' path is handled by a different, untargeted rule and should be public.
    response = client.get("/anything")
    assert response.status_code == 200

    # The '/get' path is handled by the targeted 'rule-1' and should require authentication.
    response = client.get("/get")
    assert response.status_code == 401

    # The '/get' path with a valid token should be allowed.
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
