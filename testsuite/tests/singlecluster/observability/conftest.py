"""Conftest for observability tests"""

import backoff
import pytest
from openshift_client import selector


@pytest.fixture(scope="module")
def authorization():
    """Override the authorization fixture to prevent the creation of an AuthPolicy"""
    return None


@pytest.fixture(scope="module")
def rate_limit():
    """Override the rate limit fixture to prevent the creation of an RateLimitPolicy"""
    return None


@pytest.fixture(scope="module")
def configure_observability(kuadrant):
    """Configures observability (enable=True or False) and waits for it to be applied"""

    def _configure(enable: bool):
        kuadrant.refresh().model.spec.observability = {"enable": enable}
        kuadrant.apply()
        kuadrant.wait_for_ready()
        kuadrant.refresh()
        kuadrant.wait_until(lambda obj: obj.model.spec.observability.get("enable") == enable)
        # Verify that observability is correctly enabled or disabled
        assert kuadrant.model.spec.observability.enable == enable, f"Expected observability.enable == {enable}"

    return _configure


@pytest.fixture(scope="module")
def wait_for_monitors(cluster, testconfig):
    """Wait for ServiceMonitor and PodMonitor resources to be present or absent"""

    def _wait(present=True):
        @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
        def _inner():
            service = cluster.change_project(testconfig["service_protection"]["system_project"])
            with service.context:
                servicemonitors = selector("servicemonitor", labels={"kuadrant.io/observability": "true"}).objects()

            pod = cluster.change_project(testconfig["service_protection"]["project"])
            with pod.context:
                podmonitors = selector("podmonitor", labels={"kuadrant.io/observability": "true"}).objects()

            has_monitors = bool(servicemonitors or podmonitors)
            return has_monitors if present else not has_monitors

        return _inner()

    return _wait


@pytest.fixture(scope="module")
def get_all_monitors(cluster, testconfig):
    """Fetch all ServiceMonitor and PodMonitor resources in both system and project namespaces"""

    def _get_monitors():
        service = cluster.change_project(testconfig["service_protection"]["system_project"])
        with service.context:
            servicemonitors = selector("servicemonitors").objects()

        pod = cluster.change_project(testconfig["service_protection"]["project"])
        with pod.context:
            podmonitors = selector("podmonitors").objects()

        return servicemonitors, podmonitors

    return _get_monitors


@pytest.fixture(scope="module")
def reset_observability(request, kuadrant):
    """Resets observability to default"""

    def _reset():
        kuadrant.refresh().model.spec.observability = None
        kuadrant.apply()
        kuadrant.wait_for_ready()
        kuadrant.refresh()

    request.addfinalizer(_reset)
    return _reset
