"""Configure all the components through Kuadrant,
 all methods are placeholders for now since we do not work with Kuadrant"""

import pytest
from openshift_client import OpenShiftPythonException, selector

from testsuite.backend.httpbin import Httpbin
from testsuite.gateway import GatewayRoute, Gateway, Hostname
from testsuite.gateway.envoy import Envoy
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.openshift.kuadrant import KuadrantCR
from testsuite.policy.authorization.auth_policy import AuthPolicy
from testsuite.policy.rate_limit_policy import RateLimitPolicy


@pytest.fixture(scope="session")
def openshift(hub_openshift):
    """OpenShift client for the primary namespace"""
    return hub_openshift


@pytest.fixture(scope="session")
def openshift2(testconfig, skip_or_fail):
    """OpenShift client for the secondary namespace located on the same cluster as primary Openshift"""
    client = testconfig["cluster"]
    client.change_project(testconfig["service_protection"]["project"])
    if client is None:
        skip_or_fail("Openshift2 required but second_project was not set")
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace for Openshift2 doesn't exist")
    return client


@pytest.fixture(scope="module")
def authorization_name(blame):
    """Name of the Authorization resource, can be overriden to include more dependencies"""
    return blame("authz")


@pytest.fixture(scope="module")
def authorization(kuadrant, route, authorization_name, openshift, label):
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    if kuadrant:
        return AuthPolicy.create_instance(openshift, authorization_name, route, labels={"testRun": label})
    return None


@pytest.fixture(scope="module")
def rate_limit(kuadrant, openshift, blame, request, module_label, route, gateway):  # pylint: disable=unused-argument
    """
    Rate limit object.
    Request is used for indirect parametrization, with two possible parameters:
        1. `route` (default)
        2. `gateway`
    """
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        return RateLimitPolicy.create_instance(openshift, blame("limit"), target_ref, labels={"testRun": module_label})
    return None


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()


@pytest.fixture(scope="session")
def kuadrant(request, testconfig):
    """Returns Kuadrant instance if exists, or None"""
    if request.config.getoption("--standalone"):
        return None

    ocp = testconfig["service_protection"]["project"]
    project = testconfig["service_protection"]["system_project"]
    kuadrant_openshift = ocp.change_project(project)

    try:
        with kuadrant_openshift.context:
            kuadrant = selector("kuadrant").object(cls=KuadrantCR)
            kuadrant.committed = True
    except OpenShiftPythonException:
        pytest.fail("Running Kuadrant tests, but Kuadrant resource was not found")

    return kuadrant


@pytest.fixture(scope="session")
def backend(request, openshift, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(openshift, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="session")
def gateway(request, kuadrant, openshift, blame, label, testconfig, wildcard_domain) -> Gateway:
    """Deploys Gateway that wires up the Backend behind the reverse-proxy and Authorino instance"""
    if kuadrant:
        gw = KuadrantGateway.create_instance(openshift, blame("gw"), wildcard_domain, {"app": label})
    else:
        authorino = request.getfixturevalue("authorino")
        gw = Envoy(
            openshift,
            blame("gw"),
            authorino,
            testconfig["service_protection"]["envoy"]["image"],
            labels={"app": label},
        )
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname(gateway, exposer, blame) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(blame("hostname"), gateway)
    return hostname


@pytest.fixture(scope="module")
def route(request, kuadrant, gateway, blame, hostname, backend, module_label) -> GatewayRoute:
    """Route object"""
    if kuadrant:
        route = HTTPRoute.create_instance(gateway.openshift, blame("route"), gateway, {"app": module_label})
    else:
        route = EnvoyVirtualRoute.create_instance(gateway.openshift, blame("route"), gateway)
    route.add_hostname(hostname.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def client(route, hostname):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests"""
    client = hostname.client()
    yield client
    client.close()
