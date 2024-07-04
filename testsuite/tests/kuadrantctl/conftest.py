"""Conftest for kuadrantctl tests"""

import shutil
from importlib import resources

import pytest
import yaml

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrantctl import KuadrantCTL
from testsuite.oas import OASWrapper


@pytest.fixture(scope="session")
def kuadrantctl(testconfig, skip_or_fail):
    """Return Kuadrantctl wrapper"""
    binary_path = testconfig["kuadrantctl"]
    if not shutil.which(binary_path):
        skip_or_fail("Kuadrantctl binary not found")
    return KuadrantCTL(binary_path)


@pytest.fixture(scope="module")
def oas():
    """
    OpenAPISpecification definition
    """
    return OASWrapper(
        yaml.safe_load(resources.files("testsuite.resources.oas").joinpath("base_httpbin.yaml").read_text())
    )


@pytest.fixture(scope="function")
def route(request, kuadrantctl, oas, cluster):
    """Generates Route from OAS"""
    result = kuadrantctl.run("generate", "gatewayapi", "httproute", "--oas", "-", input=oas.as_yaml(), check=False)
    assert result.returncode == 0, f"Unable to create Route from OAS: {result.stderr}"
    route = cluster.apply_from_string(result.stdout, HTTPRoute, cmd_args="--validate=false")
    request.addfinalizer(route.delete)
    return route


@pytest.fixture(scope="function")
def client(hostname, route):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = hostname.client()
    yield client
    client.close()
