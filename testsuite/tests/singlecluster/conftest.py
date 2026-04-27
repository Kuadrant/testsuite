"""Configure all the components through Kuadrant,
all methods are placeholders for now since we do not work with Kuadrant"""

import uuid
from importlib import resources

import pytest
from openshift_client import selector

from testsuite.backend.mockserver import MockserverBackend, MockserverBackendConfig
from testsuite.config import settings
from testsuite.gateway import GatewayRoute, Gateway, Hostname, GatewayListener
from testsuite.gateway.envoy import Envoy
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.exposers import OpenShiftExposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant import KuadrantCR
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.service import Service, ServicePort
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
        return AuthPolicy.create_instance(cluster, blame("authz"), target_ref, labels={"testRun": label})
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
def backend(request, cluster, blame, label, mockserver_config):
    """Deploys MockServer backend"""
    mockserver = MockserverBackend(
        cluster, blame("mockserver"), label, service_type="ClusterIP", config=mockserver_config
    )
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    return mockserver


@pytest.fixture(scope="session")
def backend_mockserver(request, backend, cluster, blame, exposer):
    """Mockserver API client for the backend, bypassing the gateway"""
    match_labels = {"app": backend.label, "deployment": backend.name}

    if isinstance(exposer, OpenShiftExposer):
        route = OpenshiftRoute.create_instance(cluster, blame("ms-api"), backend.name, "http")
        request.addfinalizer(route.delete)
        route.commit()
        base_url = f"http://{route.hostname}"
    else:
        api_service = Service.create_instance(
            cluster,
            blame("ms-api"),
            selector=match_labels,
            ports=[ServicePort(name="http", port=8080, targetPort="api")],
            labels={"app": backend.label},
            service_type="LoadBalancer",
        )
        request.addfinalizer(api_service.delete)
        api_service.commit()
        api_service.wait_for_ready(slow_loadbalancers=settings["control_plane"]["slow_loadbalancers"])
        base_url = f"http://{api_service.refresh().external_ip}:8080"

    with KuadrantClient(base_url=base_url) as http_client:
        yield Mockserver(http_client)


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
def _leak_tracker():
    """Accumulates tracking IDs of denied requests (401/403/429) for leak detection"""
    return []


DENIED_STATUS_CODES = {401, 403, 429}
TRACKING_HEADER = "X-Testsuite-Tracking"


@pytest.fixture(scope="module")
def client(route, hostname, _leak_tracker):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests, with upstream leak tracking"""

    def _inject_tracking_header(request):
        request.headers[TRACKING_HEADER] = str(uuid.uuid4())

    def _record_denied_response(response):
        if response.status_code in DENIED_STATUS_CODES:
            tracking_id = response.request.headers.get(TRACKING_HEADER)
            if tracking_id:
                _leak_tracker.append(tracking_id)

    client = hostname.client(event_hooks={"request": [_inject_tracking_header], "response": [_record_denied_response]})
    yield client
    client.close()


@pytest.fixture(scope="module", autouse=True)
def _assert_no_upstream_leak(_leak_tracker, backend_mockserver):
    """Asserts that requests denied by the gateway (401/403/429) did not reach the backend"""
    yield

    if not _leak_tracker:
        return

    denied_set = set(_leak_tracker)
    all_requests = backend_mockserver.retrieve_all_requests()

    leaked = []
    for req in all_requests:
        headers = req.get("headers", {})
        for name, values in headers.items():
            if name.lower() == TRACKING_HEADER.lower() and values:
                if values[0] in denied_set:
                    leaked.append(values[0])

    assert not leaked, (
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
