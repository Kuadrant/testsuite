"""
Test for JWT plain identity implementing user story from :
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/envoy-jwt-authn-and-authorino.md
"""

import pytest

from testsuite.kuadrant.policy.authorization import Pattern
from testsuite.gateway.envoy.jwt_plain_identity import JwtEnvoy


pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def authorization(authorization, realm_role):
    """
    Setup AuthConfig to retrieve identity from given path.
    Adds authorization rule to start geofence when user doesn't have realm role assign.
    In case of geofence user without role can only access from /anything/SK path parameter.
    """
    authorization.identity.add_plain(
        "plain", "context.metadata_context.filter_metadata.envoy\\.filters\\.http\\.jwt_authn|verified_jwt"
    )
    authorization.authorization.add_auth_rules(
        "geofence",
        [Pattern("context.request.http.path", "eq", "/anything/SK")],
        when=[Pattern("auth.identity.realm_access.roles", "excl", realm_role["name"])],
    )
    return authorization


@pytest.fixture(scope="module")
def gateway(request, authorino, cluster, blame, module_label, testconfig, keycloak, backend):
    """Deploys Envoy with additional JWT plain identity test setup"""
    envoy = JwtEnvoy(
        cluster,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        keycloak.realm_name,
        keycloak.server_url,
        backend.url,
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


def test_jwt_user_story(client, auth, auth2):
    """
    A user without an assigned role can access only from an allowed path parameter
    or when accessing from global path parameter, that doesn't trigger external authorization.
    User with assigned role can access from anywhere.
    """

    response = client.get("/anything/SK", auth=auth)
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/CZ", auth=auth)
    assert response is not None
    assert response.status_code == 403

    response = client.get("/anything/global", auth=auth)
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/CZ", auth=auth2)
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/SK", auth=auth2)
    assert response is not None
    assert response.status_code == 200

    response = client.get("/anything/global", auth=auth2)
    assert response is not None
    assert response.status_code == 200
