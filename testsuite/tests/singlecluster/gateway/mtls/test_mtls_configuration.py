"""
Tests mTLS configuration and readiness after Kuadrant CR changes
"""

import pytest
from openshift_client import selector

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]

component_cases = [
    pytest.param(["limitador"], id="limitador-only"),
    pytest.param(["authorino"], id="authorino-only"),
    pytest.param(["limitador", "authorino"], id="both-components"),
]


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_peer_authentication_resource_applied(
    kuadrant, cluster, component, wait_for_status, reset_mtls, testconfig, rate_limit, authorization, configure_mtls
):  # pylint: disable=unused-argument
    """Verify PeerAuthentication with STRICT mode is created when mTLS is enabled"""
    configure_mtls(True)

    for comp in component:
        wait_for_status(expected=True, component=comp)

    project = cluster.change_project(testconfig["service_protection"]["system_project"])
    with project.context:
        peer_auths = selector("peerauthentication").objects()
        assert peer_auths, "No PeerAuthentication resources found"

        strict = [pa for pa in peer_auths if pa.model.spec.mtls.mode == "STRICT"]
        assert strict, "No PeerAuthentication with mtls.mode == 'STRICT'"

        for pa in strict:
            match_labels = pa.model.spec.selector.matchLabels
            assert match_labels == {
                "kuadrant.io/managed": "true"
            }, f"PeerAuthentication '{pa.name()}' has unexpected matchLabels: {match_labels}"


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_pods_have_istio_sidecar_and_labels(
    kuadrant, component, wait_for_status, wait_for_injected_pod, reset_mtls, rate_limit, authorization, configure_mtls
):  # pylint: disable=unused-argument
    """Verify component pods have istio-proxy sidecar and required labels after enabling mTLS"""
    configure_mtls(True)

    for comp in component:
        wait_for_status(expected=True, component=comp)

    for comp in component:
        pod = wait_for_injected_pod(comp)
        assert pod is not None, f"No pod with sidecar found for component '{comp}'"
        pod_name = pod.name()
        pod_labels = pod.model.metadata.labels
        container_names = [c.name for c in pod.model.spec.containers]

        assert (
            pod_labels.get("sidecar.istio.io/inject") == "true"
        ), f"{pod_name} missing label 'sidecar.istio.io/inject: true'"
        assert pod_labels.get("kuadrant.io/managed") == "true", f"{pod_name} missing label 'kuadrant.io/managed: true'"
        assert "istio-proxy" in container_names, f"{pod_name} does not have 'istio-proxy' sidecar container"


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_kuadrant_cr_reaches_ready_status(
    kuadrant, component, wait_for_status, reset_mtls, rate_limit, authorization, configure_mtls
):  # pylint: disable=unused-argument
    """Verify Kuadrant CR reaches Ready status after enabling mTLS"""
    configure_mtls(True)

    for comp in component:
        wait_for_status(expected=True, component=comp)

    ready = kuadrant.wait_until(
        lambda obj: any(c.type == "Ready" and c.status == "True" for c in obj.model.status.conditions)
    )
    assert ready, "Kuadrant CR did not reach Ready=True in time"
