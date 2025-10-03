import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.extensions.telemetry_policy import TelemetryPolicy
from testsuite.utils import extract_response
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor


@pytest.fixture(scope="session")
def limitador(kuadrant):
    """Returns Limitador CR"""
    return kuadrant.limitador


@pytest.fixture(scope="module")
def pod_monitor(cluster, testconfig, request, blame, limitador):
    """Creates Pod Monitor object to watch over '/metrics' endpoint of limitador pod"""
    project = cluster.change_project(testconfig["service_protection"]["system_project"])

    endpoints = [MetricsEndpoint("/metrics", "http")]
    monitor = PodMonitor.create_instance(project, blame("pd"), endpoints, match_labels={"app": limitador.name()})
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="module", autouse=True)
def wait_for_active_targets(prometheus, pod_monitor):
    """Waits for all endpoints in Pod Monitor to become active targets"""
    assert prometheus.is_reconciled(pod_monitor)


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    annotations = {"secret.kuadrant.io/user": "testuser"}
    return create_api_key("api-key", module_label, "IAMTESTUSER", annotations=annotations)


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Setup AuthConfig for test"""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "userid": ValueFrom("auth.identity.metadata.annotations.secret\\.kuadrant\\.io/user")
            }
        ),
    )
    return authorization


@pytest.fixture(scope="module")
def telemetry_policy(request, cluster, blame, gateway):
    telemetry_policy = TelemetryPolicy.create_instance(cluster, blame("tp"), gateway)
    telemetry_policy.add_label("path", "request.path")
    telemetry_policy.add_label("user", "auth.identity.userid")
    return telemetry_policy


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("multiple", [Limit(3, "10s")])
    return rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, telemetry_policy, rate_limit):
    """Commits all important stuff before tests"""
    for component in [authorization, telemetry_policy, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()