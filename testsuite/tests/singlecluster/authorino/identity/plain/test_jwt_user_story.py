"""
Test for JWT plain identity implementing user story from :
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/envoy-jwt-authn-and-authorino.md
"""

import time
import pytest

from testsuite.kuadrant.policy.authorization import Pattern, ValueFrom, DenyResponse
from testsuite.gateway.envoy.jwt_plain_identity import JwtEnvoy


pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def mockserver_expectation(request, mockserver, module_label):
    """Creates a MockServer expectation with a VELOCITY template that responds with
    different mock JSON responses based on the 'country' query parameter."""

    velocity_template = """
    #set($country = $request.queryStringParameters['country'][0])
    #if($country == "GB")
    {
      "statusCode": 200,
      "headers": {
        "Content-Type": "application/json"
      },
      "body": "{ \\"country_iso_code\\": \\"GB\\", \\"country_name\\": \\"Great Britain\\" }"
    }
    #elseif($country == "IT")
    {
      "statusCode": 200,
      "headers": {
        "Content-Type": "application/json"
      },
      "body": "{ \\"country_iso_code\\": \\"IT\\", \\"country_name\\": \\"Italy\\" }"
    }
    #end
    """
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    expectation = mockserver.create_template_expectation(module_label, velocity_template, template_type="VELOCITY")
    return expectation + "?country={context.request.http.headers.x-country}"


@pytest.fixture(scope="module")
def authorization(authorization, realm_role, mockserver_expectation):
    """
    Add to the AuthConfig:
        - retrieve identity from the specified path
        - add HTTP metadata from the MockServer
        - define an authorization rule to enable geofence when the user doesn't have the assigned realm role
        - set a custom deny message for unauthorized responses
    """
    authorization.identity.add_plain(
        "plain", "context.metadata_context.filter_metadata.envoy\\.filters\\.http\\.jwt_authn|verified_jwt"
    )
    authorization.metadata.add_http("geoinfo", mockserver_expectation, "GET")
    authorization.authorization.add_auth_rules(
        "geofence",
        [Pattern("auth.metadata.geoinfo.country_iso_code", "eq", "GB")],
        when=[Pattern("auth.identity.realm_access.roles", "excl", realm_role["name"])],
    )
    authorization.responses.set_unauthorized(
        DenyResponse(
            message=ValueFrom("The requested resource is not available in " + "{auth.metadata.geoinfo.country_name}"),
        )
    )
    return authorization


@pytest.fixture(scope="module")
def gateway(request, authorino, cluster, blame, module_label, testconfig, keycloak):
    """Deploys Envoy with additional JWT plain identity test setup."""
    envoy = JwtEnvoy(
        cluster,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        keycloak.realm_name,
        keycloak.server_url,
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def route(route, backend):
    """Add specific route match for JWT test into EnvoyConfig."""
    route_dictionary = {
        "match": {"path_separated_prefix": "/anything/global"},
        "route": {"cluster": backend.url},
        "typed_per_filter_config": {
            "envoy.filters.http.ext_authz": {
                "@type": "type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthzPerRoute",
                "disabled": True,
            }
        },
    }
    route.add_custom_routes_match(match=route_dictionary)
    time.sleep(5)
    return route


def test_jwt_user_story(client, auth, auth2):
    """
    A user without an assigned realm role can access only with the allowed country parameter
    or when accessing from global path parameter, that doesn't trigger external authorization.
    User with assigned role can access all paths, regardless of the country parameter.
    """

    response = client.get("/get", auth=auth, headers={"x-country": "GB"})
    assert response is not None
    assert response.status_code == 200

    response = client.get("/get", auth=auth, headers={"x-country": "IT"})
    assert response is not None
    assert response.status_code == 403
    deny_message = response.headers.get("x-ext-auth-reason")
    assert deny_message == "The requested resource is not available in Italy"

    response = client.get("/anything/global", auth=auth)
    assert response is not None
    assert response.status_code == 200

    response = client.get("/get", auth=auth2, headers={"x-country": "GB"})
    assert response is not None
    assert response.status_code == 200

    response = client.get("/get", auth=auth2, headers={"x-country": "IT"})
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/global", auth=auth2)
    assert response is not None
    assert response.status_code == 200
