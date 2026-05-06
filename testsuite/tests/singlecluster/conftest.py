"""Configure all the components through Kuadrant,
all methods are placeholders for now since we do not work with Kuadrant"""

import logging
from importlib import resources

import httpx
import pytest
from openshift_client import selector

from testsuite.backend.mockserver import MockserverBackend, MockserverBackendConfig
from testsuite.gateway import GatewayRoute, Gateway, Hostname, GatewayListener
from testsuite.gateway.envoy import Envoy
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant import KuadrantCR
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient
from testsuite.mockserver import Mockserver


@pytest.fixture(scope="session")
def second_namespace(testconfig, skip_or_fail) -> KubernetesClient:
    """Kubernetes client for the secondary namespace located on the same cluster as primary cluster"""
    project = testconfig["service_protection"]["project2"]
    client = testconfig["control_plane"]["cluster"].change_project(testconfig["service_protection"]["project2"])
    if client is None:
        skip_or_fail("Tests requires second_project but service_protection.project2 is not set")
    if not client.connected:
        pytest.fail(f"You are not logged into Kubernetes or the namespace for {project} doesn't exist")
    return client


@pytest.fixture(scope="module")
def authorization_name(blame):
    """Name of the Authorization resource, can be overriden to include more dependencies"""
    return blame("authz")


@pytest.fixture(scope="module")
def authorization(request, kuadrant, route, gateway, blame, cluster, label):  # pylint: disable=unused-argument
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        return AuthPolicy.create_instance(cluster, blame("authz"), gateway, labels={"testRun": label})
    return None


@pytest.fixture(scope="module")
def rate_limit(kuadrant, cluster, blame, request, module_label, route, gateway):  # pylint: disable=unused-argument
    """
    Rate limit object.
    Request is used for indirect parametrization, with two possible parameters:
        1. `route` (default)
        2. `gateway`
    """
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        return RateLimitPolicy.create_instance(cluster, blame("limit"), target_ref, labels={"testRun": module_label})
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
def kuadrant(request, system_project):
    """Returns Kuadrant instance if exists, or None"""
    if request.config.getoption("--standalone"):
        return None

    with system_project.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)

    return kuadrant


@pytest.fixture(scope="session")
def mockserver_config(cluster, blame, label):
    """Initial MockServer configuration with echo expectation"""
    echo_json = resources.files("testsuite.resources").joinpath("echo_expectation.json").read_text()
    config = MockserverBackendConfig(
        cluster,
        blame("mockserver-config"),
        label,
        data={"echo_expectation.json": echo_json},
    )
    config.commit()
    return config


@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, mockserver_config, testconfig):
    """Deploys MockServer backend"""
    mockserver = MockserverBackend(cluster, blame("mockserver"), label, config=mockserver_config)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()

    backend_exposer = testconfig["default_exposer"](cluster)
    request.addfinalizer(backend_exposer.delete)
    backend_exposer.commit()
    mockserver.expose(backend_exposer, blame("backend"))
    return mockserver


@pytest.fixture(scope="session")
def gateway(request, kuadrant, cluster, blame, label, testconfig, wildcard_domain) -> Gateway:
    """Deploys Gateway that wires up the Backend behind the reverse-proxy and Authorino instance"""
    if kuadrant:
        gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
        gw.add_listener(GatewayListener(hostname=wildcard_domain))
    else:
        authorino = request.getfixturevalue("authorino")
        gw = Envoy(
            cluster,
            blame("gw"),
            authorino,
            testconfig["service_protection"]["envoy"]["image"],
            labels={"app": label},
        )
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="session")
def backend_hostname(backend) -> Hostname:
    """Exposed hostname pointing directly at the backend, bypassing the gateway"""
    return backend.admin_hostname


@pytest.fixture(scope="module")
def domain_name(blame) -> str:
    """Domain name"""
    return blame("hostname")


@pytest.fixture(scope="module")
def hostname(gateway, exposer, domain_name) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(domain_name, gateway)
    return hostname


@pytest.fixture(scope="module")
def route(request, kuadrant, gateway, blame, hostname, backend, module_label) -> GatewayRoute:
    """Route object"""
    if kuadrant:
        route = HTTPRoute.create_instance(gateway.cluster, blame("route"), gateway, {"app": module_label})
    else:
        route = EnvoyVirtualRoute.create_instance(gateway.cluster, blame("route"), gateway)
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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pylint: disable=unused-argument
    """Verifies that denied requests did not leak to the upstream backend"""
    outcome = yield
    report = outcome.get_result()

    if call.when != "call" or not report.passed:
        return

    client = item.funcargs.get("client")
    backend = item.funcargs.get("backend")
    if client is None or backend is None or backend.admin_hostname is None:
        return

    denied_ids = set(client.denied_request_ids)
    client.denied_request_ids.clear()
    if not denied_ids:
        return

    backend_client = backend.admin_hostname.client()
    ms = Mockserver(backend_client)
    tracking_header = KuadrantClient.TRACKING_HEADER

    leaked = []
    try:
        for denied_id in denied_ids:
            if ms.retrieve_requests_by_header(tracking_header, denied_id):
                leaked.append(denied_id)
    except (httpx.RequestError, httpx.HTTPStatusError):
        logging.warning("Failed to check for upstream leaks via MockServer", exc_info=True)
        return
    finally:
        backend_client.close()

    if leaked:
        report.outcome = "failed"
        report.longrepr = (
            f"{len(leaked)} denied request(s) leaked to the upstream backend. "
            f"The gateway returned a denial status (401/403/429) but the request still reached MockServer."
        )


@pytest.fixture(scope="module")
def create_api_key(blame, request, cluster):
    """Creates API key Secret"""

    def _create_secret(
        name, label_selector, api_key, ocp: KubernetesClient = cluster, annotations: dict[str, str] = None
    ):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key, annotations)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret
