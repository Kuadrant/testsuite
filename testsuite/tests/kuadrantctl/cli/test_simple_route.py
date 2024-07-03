"""Tests that you can generate simple HTTPRoute, focused on the cmdline options more than on extension functionality"""

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.oas import as_tmp_file


@pytest.fixture(scope="module")
def route():
    """Make sure Route is not created automatically"""
    return None


@pytest.fixture(scope="module")
def oas(oas, blame, gateway, hostname, backend):
    """Add Route and Backend specifications to OAS"""
    oas["x-kuadrant"] = {
        "route": {
            "name": blame("route"),
            "hostnames": [hostname.hostname],
            "parentRefs": [gateway.reference],
        }
    }
    oas.add_backend_to_paths(backend)
    return oas


@pytest.mark.parametrize("encoder", [pytest.param("as_json", id="JSON"), pytest.param("as_yaml", id="YAML")])
@pytest.mark.parametrize("stdin", [pytest.param(True, id="STDIN"), pytest.param(False, id="File")])
def test_generate_route(request, kuadrantctl, oas, encoder, openshift, client, stdin):
    """Tests that Route can be generated and that is works as expected"""
    encoded = getattr(oas, encoder)()

    if stdin:
        result = kuadrantctl.run("generate", "gatewayapi", "httproute", "--oas", "-", input=encoded)
    else:
        with as_tmp_file(encoded) as file_name:
            result = kuadrantctl.run("generate", "gatewayapi", "httproute", "--oas", file_name)

    # https://github.com/Kuadrant/kuadrantctl/issues/91
    route = openshift.apply_from_string(result.stdout, HTTPRoute, cmd_args="--validate=false")
    # route = openshift.apply_from_string(result.stdout, HTTPRoute)
    request.addfinalizer(route.delete)
    route.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200

    response = client.get("/anything")
    assert response.status_code == 200

    response = client.put("/anything")
    assert response.status_code == 200

    # Incorrect methods
    response = client.post("/anything")
    assert response.status_code == 404

    # Incorrect path
    response = client.get("/anything/test")
    assert response.status_code == 404

    # Incorrect endpoint
    response = client.post("/post")
    assert response.status_code == 404
