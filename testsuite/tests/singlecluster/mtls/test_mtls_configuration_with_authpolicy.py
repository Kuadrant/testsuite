"""
Tests mTLS configuration and readiness after Kuadrant CR changes (authpolicy)
"""

import pytest

from openshift_client import selector

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    return None


def test_peer_authentication_resource_applied_auth_policy(
    kuadrant, cluster, authorization, wait_for_mtls_status, reset_mtls
):  # pylint: disable=unused-argument
    """Verify PeerAuthentication with STRICT mode is created when mTLS is enabled"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="authorino")

    project = cluster.change_project("kuadrant-system")
    with project.context:
        peer_auths = selector("peerauthentication").objects()
    assert peer_auths, "No PeerAuthentication resources found"

    strict = [pa.name() for pa in peer_auths if pa.model.spec.mtls.mode == "STRICT"]
    assert strict, "No PeerAuthentication with mtls.mode == 'STRICT'"


def test_authorino_pods_have_istio_sidecar_and_labels(
    kuadrant, cluster, authorization, wait_for_mtls_status, wait_for_injected_pod, reset_mtls
):  # pylint: disable=unused-argument
    """Verify Authorino pods have istio-proxy sidecar and required labels after enabling mTLS"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="authorino")

    pod = wait_for_injected_pod("authorino")
    pod_name = pod.name()
    pod_labels = pod.model.metadata.labels
    container_names = [c.name for c in pod.model.spec.containers]

    assert pod_labels["sidecar.istio.io/inject"] == "true", f"{pod_name} missing label 'sidecar.istio.io/inject: true'"
    assert pod_labels["kuadrant.io/managed"] == "true", f"{pod_name} missing label 'kuadrant.io/managed: true'"
    assert "istio-proxy" in container_names, f"{pod_name} does not have 'istio-proxy' sidecar container"


def test_kuadrant_cr_reaches_ready_status_auth_policy(
    kuadrant, authorization, wait_for_mtls_status, reset_mtls
):  # pylint: disable=unused-argument
    """Verify Kuadrant CR reaches Ready status after enabling mTLS"""
    kuadrant.refresh().model.spec.mtls = {"enable": True}
    kuadrant.apply()
    kuadrant.wait_for_ready()
    wait_for_mtls_status(kuadrant, expected=True, component="authorino")

    ready = kuadrant.wait_until(
        lambda obj: any(c.type == "Ready" and c.status == "True" for c in obj.model.status.conditions)
    )
    assert ready, "Kuadrant CR did not reach Ready=True in time"
