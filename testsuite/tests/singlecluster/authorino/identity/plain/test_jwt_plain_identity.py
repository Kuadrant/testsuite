"""
Plain identity test with automation handled by Envoy leveraging the Envoy JWT Authentication filter
(decoded JWT injected as 'metadata_context' into the response).
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/envoy-jwt-authn-and-authorino.md
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.gateway.envoy.jwt_plain_identity import JwtEnvoy
from testsuite.utils import extract_response


pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def realm_role(keycloak, blame):
    """Creates new realm role"""
    return keycloak.realm.create_realm_role(blame("role"))


@pytest.fixture(scope="module")
def user_with_role(keycloak, realm_role, blame):
    """Creates new user and adds him into realm_role"""
    username = blame("someuser")
    password = blame("password")
    user = keycloak.realm.create_user(username, password)
    user.assign_realm_role(realm_role)
    return user


@pytest.fixture(scope="module")
def authorization(authorization, realm_role, blame):
    """
    Setup AuthConfig to retrieve identity from given path.
    Adds rule, that requires user to be part of realm_role to be allowed access.
    """
    authorization.identity.add_plain(
        "plain", "context.metadata_context.filter_metadata.envoy\\.filters\\.http\\.jwt_authn|verified_jwt"
    )
    authorization.responses.add_simple("context.metadata_context.filter_metadata")
    authorization.authorization.add_role_rule(blame("rule"), realm_role["name"], "^/get")
    return authorization


@pytest.fixture(scope="module")
def gateway(request, authorino, cluster, blame, module_label, testconfig, keycloak):
    """Deploys Envoy with additional JWT plain identity test setup"""
    envoy = JwtEnvoy(
        cluster,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        testconfig["tools"].project,
        keycloak.realm_name,
        keycloak.server_url,
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def auth2(user_with_role, keycloak):
    """Creates user with role and returns its authentication object for HTTPX"""
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user_with_role, "authorization")


def test_jwt_plain_identity(client, auth2, auth, keycloak):
    """
    Test assertions for corresponding status codes:
    - user has assigned role and valid token is passed through
    - user doesn't have assigned role
    - invalid token
    """

    response = client.get("/get", auth=auth2)
    assert response is not None
    assert response.status_code == 200
    extracted_iss = (extract_response(response) % None)["envoy.filters.http.jwt_authn"]["verified_jwt"]["iss"]
    assert extracted_iss == f"{keycloak.server_url}/realms/{keycloak.realm_name}"

    response = client.get("/get", auth=auth)
    assert response is not None
    assert response.status_code == 403

    response = client.get("/get", headers={"Authorization": "Bearer invalid-token123"})
    assert response is not None
    assert response.status_code == 401
