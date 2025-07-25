"""
This module contains tests for auto-scaling the gateway deployment with an HPA watching the cpu usage
"""

import time

import pytest


from testsuite.kubernetes.horizontal_pod_autoscaler import HorizontalPodAutoscaler

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def setup_rbac(request, custom_metrics_sa, custom_metrics_server_role, custom_metrics_reader_role, rbac_bindings):
    """Commits all RBAC resources needed for the prometheus adapter"""
    components = [custom_metrics_server_role, custom_metrics_reader_role, custom_metrics_sa, *rbac_bindings]

    # Add finalizers for all components
    for component in components:
        request.addfinalizer(component.delete)

    # Commit roles first
    for role in [custom_metrics_server_role, custom_metrics_reader_role]:
        role.commit()
        if hasattr(role, "wait_for_ready"):
            role.wait_for_ready()

    # Commit service account
    custom_metrics_sa.commit()
    if hasattr(custom_metrics_sa, "wait_for_ready"):
        custom_metrics_sa.wait_for_ready()

    # Commit all bindings
    for binding in rbac_bindings:
        binding.commit()
        if hasattr(binding, "wait_for_ready"):
            binding.wait_for_ready()

    return components


@pytest.fixture(scope="module")
def hpa(cluster, blame, gateway, module_label):
    """Add hpa to the gateway deployment"""
    hpa = HorizontalPodAutoscaler.create_instance(
        cluster,
        blame("hpa"),
        gateway.deployment,
        [
            {
                "type": "Pods",
                "pods": {
                    "metric": {"name": "istio_requests"},
                    "target": {"type": "Value", "averageValue": "10"},
                },
            }
        ],
        labels={"app": module_label},
        min_replicas=1,
        max_replicas=5,
    )
    return hpa


@pytest.fixture(scope="module")
def prometheus_stack(
    request,
    prometheus,
    pod_monitor,
    setup_rbac,  # pylint: disable=unused-argument
    prometheus_adapter_service,
    prometheus_adapter_api_service,
    adapter_config,
    prometheus_config,
    prometheus_adapter_deployment,
    hpa,
):
    """Create and commit the prometheus stack"""
    components = [
        pod_monitor,
        prometheus_adapter_service,
        prometheus_adapter_api_service,
        adapter_config,
        prometheus_config,
        prometheus_adapter_deployment,
    ]

    # Add finalizers for all components
    for component in components:
        request.addfinalizer(component.delete)

    # Commit all components
    for component in components:
        component.commit()
        if hasattr(component, "wait_for_ready"):
            component.wait_for_ready()

    assert prometheus.is_reconciled(pod_monitor)
    prometheus.wait_for_scrape(pod_monitor, "/stats/prometheus")

    # Commit HPA latest to avoid idling without metrics
    request.addfinalizer(hpa.delete)
    hpa.commit()

    return components


def test_auto_scale_gateway(gateway, prometheus_stack, client, auth):  # pylint: disable=unused-argument
    """This test asserts that the policies are working as expected and this behavior does not change after scaling"""
    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 10, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429

    time.sleep(5)  # sleep in order to reset the rate limit policy time limit.

    gateway.deployment.wait_for_replicas(2)

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401

    responses = client.get_many("/get", 10, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
