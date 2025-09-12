"""Conftest for kuadrantctl tests"""

import shutil
from importlib import resources

import pytest
import yaml

from testsuite.backend.httpbin import Httpbin
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.gateway import Gateway, GatewayListener, Hostname
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
    """OpenAPISpecification definition"""
    return OASWrapper(
        yaml.safe_load(resources.files("testsuite.resources.oas").joinpath("base_httpbin.yaml").read_text())
    )


@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys Httpbin backend"""
    image = testconfig["httpbin"]["image"]
    httpbin = Httpbin(cluster, blame("httpbin"), label, image)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="session")
def gateway(request, cluster, blame, label, wildcard_domain) -> Gateway:
    """Deploys Gateway that wires up the Backend behind the reverse-proxy and Authorino instance"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname(gateway, exposer, blame) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(blame("hostname"), gateway)
    return hostname


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
