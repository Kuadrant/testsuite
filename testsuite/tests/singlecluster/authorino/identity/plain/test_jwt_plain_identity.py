"""
Plain identity test with automation handled by Envoy leveraging the Envoy JWT Authentication filter
(decoded JWT injected as 'metadata_context' into the response).
"""

import pytest

from testsuite.utils import extract_response
from testsuite.gateway.envoy.jwt_plain_identity import JwtEnvoy

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def authorization(authorization, realm_role, blame):
    """
    Setup AuthConfig to retrieve identity from given path.
    Adds rule, that requires user to be part of realm_role to be allowed access.
    """
    authorization.identity.add_plain(
        "plain", "context.metadata_context.filter_metadata.envoy\\.filters\\.http\\.jwt_authn|verified_jwt"
    )
    authorization.authorization.add_role_rule(blame("rule"), realm_role["name"], "^/get")
    authorization.responses.add_simple("context.metadata_context.filter_metadata")
    return authorization


@pytest.fixture(scope="module")
def gateway(request, authorino, cluster, blame, module_label, testconfig, keycloak):
    """Deploys Envoy with additional JWT plain identity test setup"""
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
