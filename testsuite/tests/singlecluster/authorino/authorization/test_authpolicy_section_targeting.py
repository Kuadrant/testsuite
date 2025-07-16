"""
Tests that the AuthPolicy is correctly applied:

First:
- The AuthPolicy is applied only to a specific *listener section* of the Gateway (section_name = 'api')-
  The policy applies authentication only to requests matching path '/get'
- Requests to other paths (e.g., '/anything') are public
- CEL predicates further restrict the policy scope (e.g. only for '/get' path)

Second:
   - The AuthPolicy is applied only to a specific *rule section* in an HTTPRoute (section_name = 'rule-1')
   - Only the path handled by that rule (again, '/get') is protected
   - The policy does not affect the other rule sections (e.g., for '/anything')
"""

import pytest
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy import CelPredicate


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def route(route, backend):
    """Override default route to have two backends with different paths"""
    route.remove_all_rules()
    route.add_backend(backend, "/get")  # This backend path will be protected
    route.add_backend(backend, "/anything")  # This backend path will be public
    return route


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, gateway, oidc_provider, route):  # pylint: disable=unused-argument
    """Create AuthPolicy that applies only to the 'api' section of the Gateway.
    Auth is required only for requests with path '/get'"""
    policy = AuthPolicy.create_instance(
        cluster,
        blame("authz"),
        gateway,
        section_name="api",  # bind to specific listener section
        labels={"testRun": module_label},
    )
    # Require OIDC authentication for selected requests
    policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])

    # Apply the policy only when the request path matches '/get'
    policy.add_rule([CelPredicate("request.path == '/get'")])

    return policy


@pytest.fixture(scope="module")
def route_http_route(route, backend):
    """HTTPRoute with two rule sections - each pointing to a different path"""
    route.remove_all_rules()
    route.add_rule(backend, path_prefix="/get", rule_name="rule-1")  # Protected
    route.add_rule(backend, path_prefix="/anything", rule_name="rule-2")  # Public
    return route


@pytest.fixture(scope="module")
def authorization_http_route(cluster, blame, module_label, route_http_route, oidc_provider):
    """AuthPolicy is bound to a specific section (rule) in the HTTPRoute.
    The policy applies only to the rule named 'rule-1', and only for path '/get'.
    = Only requests handled by rule-1 and matching '/get' will require auth
    """
    policy = AuthPolicy.create_instance(
        cluster,
        blame("authz-hr"),
        route_http_route,
        section_name="rule-1",  # Bind policy to specific rule in HTTPRoute
        labels={"testRun": module_label},
    )
    policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    policy.add_rule([CelPredicate("request.path == '/get'")])
    return policy


def test_auth_policy_applies_only_to_protected_path(client, auth):
    """Test that AuthPolicy protects only the /get path"""

    # /anything - unprotected path should be accessible without authentication
    response = client.get("/anything")
    assert response.status_code == 200

    # /get should require authentication, without token expect 401
    response = client.get("/get")
    assert response.status_code == 401

    # /get - protected path with valid token should allow requests
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_auth_policy_applies_only_to_http_route_section(client, auth):
    """
    Tests that the AuthPolicy bound to HTTPRoute section only protects the '/get' path.
    """
    response = client.get("/anything")
    assert response.status_code == 200  # Public path should be accessible
    response = client.get("/get")
    assert response.status_code == 401  # Protected path should return 401 without token
    response = client.get("/get", auth=auth)
    assert response.status_code == 200  # Protected path should be accessible with token
