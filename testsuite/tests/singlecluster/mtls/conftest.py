"""Conftest for mTLS tests"""

import time

import pytest

from openshift_client import selector
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def authorization(oidc_provider, gateway, cluster, blame, module_label, route):  # pylint: disable=unused-argument
    """Overwrite the authorization fixture for testing"""
    policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway, labels={"testRun": module_label})
    policy.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return policy


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(2, "10s")])
    return policy


@pytest.fixture(scope="module")
def wait_for_mtls_status():
    """Waits for mTLS status per component"""

    def _wait_for_mtls_status(kuadrant, expected: bool, component: str):
        key = f"mtls{component.capitalize()}"
        for _ in range(10):
            if kuadrant.refresh().model.status.get(key) == expected:
                return
            kuadrant.wait_for_ready()
        raise TimeoutError(f"mTLS status '{key}' did not reach expected value {expected}")

    return _wait_for_mtls_status


@pytest.fixture(scope="module")
def wait_for_injected_pod(cluster):
    """Waits for a sidecar-injected pod (Authorino or Limitador) in kuadrant-system namespace"""

    def _wait(component_label, timeout=30, interval=2):
        project = cluster.change_project("kuadrant-system")

        with project.context:
            for _ in range(timeout // interval):
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
                time.sleep(interval)

        raise TimeoutError(f"No ready {component_label} pod with istio-proxy sidecar found")

    return _wait


@pytest.fixture(scope="module")
def reset_mtls(request, kuadrant):
    """Resets mTLS to false"""

    def _reset():
        kuadrant.refresh().model.spec.mtls = {"enable": False}
        kuadrant.apply()
        kuadrant.wait_for_ready()

    request.addfinalizer(_reset)
