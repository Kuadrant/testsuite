"""Tests that you can generate simple AuthPolicy, focused on the cmdline options more than on extension functionality"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oas import as_tmp_file
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def auth(keycloak):
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth(keycloak.get_token, "authorization")


@pytest.fixture(scope="module")
def oas(oas, keycloak, blame, gateway, hostname, backend):
    """Add OIDC configuration"""
    oas.add_top_level_route(gateway, hostname, blame("route"))

    oas["components"] = {
        "securitySchemes": {
            "oidc": {
                "type": "openIdConnect",
                "openIdConnectUrl": keycloak.well_known["issuer"],
                # https://github.com/Kuadrant/kuadrantctl/issues/94
                # "openIdConnectUrl": keycloak.well_known["issuer"] + "/.well-known/openid-configuration",
            }
        }
    }
    anything = oas["paths"]["/anything"]
    anything["x-kuadrant"] = {
        "backendRefs": [backend.reference],
    }
    anything["get"]["security"] = [{"oidc": []}]
    return oas


@pytest.mark.parametrize("encoder", [pytest.param("as_json", id="JSON"), pytest.param("as_yaml", id="YAML")])
@pytest.mark.parametrize("stdin", [pytest.param(True, id="STDIN"), pytest.param(False, id="File")])
def test_generate_authpolicy(request, kuadrantctl, oas, encoder, cluster, client, stdin, auth):
    """Generates Policy from OAS and tests that it works as expected"""
    encoded = getattr(oas, encoder)()

    if stdin:
        result = kuadrantctl.run("generate", "kuadrant", "authpolicy", "--oas", "-", input=encoded)
    else:
        with as_tmp_file(encoded) as file_name:
            result = kuadrantctl.run("generate", "kuadrant", "authpolicy", "--oas", file_name)

    policy = cluster.apply_from_string(result.stdout, AuthPolicy)
    request.addfinalizer(policy.delete)

    policy.wait_for_ready()

    response = client.get("/anything")
    assert response.status_code == 401

    response = client.get("/anything", auth=auth)
    assert response.status_code == 200

    response = client.get("/anything", headers={"Authorization": "Bearer xyz"})
    assert response.status_code == 401

    response = client.put("/anything")
    assert response.status_code == 200
