"""Conftest for mTLS tests"""

import backoff
import pytest

from openshift_client import selector

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def component(request):
    """Active component (limitador, authorino, or both)"""
    return request.param


@pytest.fixture(scope="module")
def authorization(component, request, oidc_provider):
    """Return AuthPolicy when 'authorino' is active"""
    if "authorino" in component:
        authorization = request.getfixturevalue("authorization")
        authorization.identity.clear_all()
        authorization.identity.add_oidc(
            "default", oidc_provider.well_known["issuer"], when=[CelPredicate("request.path == '/anything/authorino'")]
        )
        # Anonymous auth for /anything/limitador
        authorization.identity.add_anonymous(
            "allow-limitador-anonymous", when=[CelPredicate("request.path == '/anything/limitador'")]
        )
        return authorization
    return None


@pytest.fixture(scope="module")
def rate_limit(component, cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """Create and return RateLimitPolicy when 'limitador' is active"""
    if "limitador" in component:
        policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
        policy.add_limit("basic", [Limit(2, "10s")], when=[CelPredicate("request.path == '/anything/limitador'")])
        return policy
    return None


@pytest.fixture(scope="module")
def wait_for_status(kuadrant):
    """Waits for mTLS status per component"""

    def _wait_for_mtls_status(expected: bool, component: str):
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
        # Verify that mTLS is correctly enabled or disabled
        assert kuadrant.model.spec.mtls.enable == enable, f"Expected mTLS.enable == {enable}"

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
