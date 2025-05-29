"""Conftest for mTLS tests"""

import backoff
import pytest

from openshift_client import selector
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def component(request):
    """Active component (limitador, authorino, or both)"""
    return request.param


@pytest.fixture(scope="module")
def authorization(component, request):
    """Enable AuthPolicy when component is 'authorino' or 'both'"""
    if component in ("authorino", "both"):
        return request.getfixturevalue("authorization")
    return None


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(2, "10s")])
    return policy


@pytest.fixture(scope="module")
def wait_for_status():
    """Waits for mTLS status per component"""

    def _wait_for_mtls_status(kuadrant, expected: bool, component: str):
        key = f"mtls{component.capitalize()}"
        kuadrant.wait_until(lambda obj: obj.model.status.get(key) == expected)

    return _wait_for_mtls_status


@pytest.fixture(scope="module")
def wait_for_injected_pod(cluster, testconfig):
    """Waits for a sidecar-injected pod (Authorino or Limitador)"""

    @backoff.on_predicate(backoff.fibo, lambda result: result is None, max_tries=7, jitter=None)
    def _wait(component_label):
        project = cluster.change_project(testconfig["service_protection"]["system_project"])
        with project.context:
            pods = selector("pods", labels={f"{component_label}-resource": component_label}).objects()
            for pod in pods:
                labels = pod.model.metadata.labels
                containers = [c.name for c in pod.model.spec.containers]

                if (
                    labels.get("sidecar.istio.io/inject") == "true"
                    and labels.get("kuadrant.io/managed") == "true"
                    and "istio-proxy" in containers
                ):
                    return pod
        return None

    return _wait


@pytest.fixture(scope="module")
def configure_mtls(kuadrant):
    """Configures mTLS (enable=True or False) and waits for it to be applied"""

    def _configure(enable: bool):
        kuadrant.refresh().model.spec.mtls = {"enable": enable}
        kuadrant.apply()
        kuadrant.wait_for_ready()
        kuadrant.refresh()

    return _configure


@pytest.fixture(scope="module")
def reset_mtls(request, kuadrant):
    """Resets mTLS to default"""

    def _reset():
        kuadrant.refresh().model.spec.mtls = None
        kuadrant.apply()
        kuadrant.wait_for_ready()
        kuadrant.refresh()

    request.addfinalizer(_reset)


def get_components_to_check(component):
    """Returns a list of components"""
    return [component] if component != "both" else ["limitador", "authorino"]
