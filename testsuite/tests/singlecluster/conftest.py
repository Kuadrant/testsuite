"""Configure all the components through Kuadrant,
all methods are placeholders for now since we do not work with Kuadrant"""

import time
import pytest
from openshift_client import selector

from testsuite.backend.httpbin import Httpbin
from testsuite.gateway import GatewayRoute, Gateway, Hostname, GatewayListener
from testsuite.gateway.envoy import Envoy
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant import KuadrantCR
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.openshift.route import OpenshiftRoute


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
def authorization(request, kuadrant, route, gateway, blame, cluster, label, metrics_route):  # pylint: disable=unused-argument
    """Authorization object (In case of Kuadrant AuthPolicy)"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        policy = AuthPolicy.create_instance(cluster, blame("authz"), target_ref, labels={"testRun": label})
        policy.set_metrics_route(metrics_route)
        return policy
    return None


@pytest.fixture(scope="module")
def rate_limit(kuadrant, cluster, blame, request, module_label, route, gateway, metrics_route):  # pylint: disable=unused-argument
    """
    Rate limit object.
    Request is used for indirect parametrization, with two possible parameters:
        1. `route` (default)
        2. `gateway`
    """
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    if kuadrant:
        policy = RateLimitPolicy.create_instance(cluster, blame("limit"), target_ref, labels={"testRun": module_label})
        policy.set_metrics_route(metrics_route)
        return policy
    return None


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()  # Automatically waits for Envoy!


@pytest.fixture(scope="session")
def kuadrant(request, testconfig):
    """Returns Kuadrant instance if exists, or None"""
    if request.config.getoption("--standalone"):
        return None

    ocp = testconfig["control_plane"]["cluster"]
    project = testconfig["service_protection"]["system_project"]
    kuadrant_openshift = ocp.change_project(project)

    with kuadrant_openshift.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)

    return kuadrant


@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys Httpbin backend"""
    image = testconfig["httpbin"]["image"]
    httpbin = Httpbin(cluster, blame("httpbin"), label, image)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


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
def metrics_route(request, gateway, cluster, blame, kuadrant):
    """Create OpenShift Route to expose gateway metrics, bypassing Gateway/OIDC/AuthPolicy.

    Only created for Kuadrant gateways. Allows checking when WASM configs are actually loaded.
    """
    if not kuadrant:
        return None

    route = OpenshiftRoute.create_instance(
        cluster,
        blame("metrics"),
        f"{gateway.name()}-metrics",  # Service name
        "metrics",  # Target port name
    )

    request.addfinalizer(route.delete)
    route.commit()

    return route


def get_kuadrant_configs_value(metrics_route):
    """Get the current value of kuadrant_configs metric.

    Args:
        metrics_route: OpenShift Route to metrics service

    Returns:
        Integer value of kuadrant_configs metric, or 0 if not found
    """
    if metrics_route is None:
        return 0

    try:
        metrics_client = metrics_route.client()
        response = metrics_client.get("/stats/prometheus")
        if response.status_code == 200:
            # Parse the metric value from lines like: kuadrant_configs{} 1
            for line in response.text.split("\n"):
                if line.startswith("kuadrant_configs{}"):
                    return int(line.split()[1])
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return 0


def wait_for_policy_applied_to_envoy(metrics_route, initial_value, timeout=120, interval=5):
    """Wait for policy to be applied in Envoy by checking for kuadrant_configs metric change.

    Uses metrics OpenShift Route which bypasses Gateway and policy enforcement.

    Args:
        metrics_route: OpenShift Route to metrics service
        initial_value: Initial value of kuadrant_configs before policy was committed
        timeout: Maximum time to wait in seconds (default: 120)
        interval: Polling interval in seconds (default: 5)

    Returns:
        True if policy is applied (kuadrant_configs increased), False if timeout reached
    """
    if metrics_route is None:
        # No metrics route available (e.g., standalone mode), skip waiting
        return True

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            current_value = get_kuadrant_configs_value(metrics_route)
            # Check if metric exists and has increased from initial value
            if current_value is not None and current_value > (initial_value or 0):
                return True
        except Exception:  # pylint: disable=broad-exception-caught
            pass  # Ignore connection errors and continue polling

        time.sleep(interval)

    return False


def commit_and_wait(request, metrics_route, *policies):
    """Helper to commit multiple policies and wait for them to be applied in Envoy.

    This is a convenience function that:
    1. Sets up cleanup (delete) for each policy
    2. Sets metrics_route for Envoy waiting
    3. Commits the policy
    4. Waits for K8s ready + Envoy application

    Args:
        request: pytest request fixture (for finalizers)
        metrics_route: OpenShift Route to gateway metrics
        *policies: Variable number of policy objects to commit

    Example:
        @pytest.fixture(scope="module", autouse=True)
        def commit(request, metrics_route, authorization, rate_limit):
            commit_and_wait(request, metrics_route, authorization, rate_limit)
    """
    for policy in policies:
        if policy is not None:
            request.addfinalizer(policy.delete)
            policy.set_metrics_route(metrics_route)
            policy.commit()
            policy.wait_for_ready()


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
