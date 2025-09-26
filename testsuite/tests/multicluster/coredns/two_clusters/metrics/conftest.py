"""Conftest for DNS Operator metrics tests"""

import pytest

from testsuite.kubernetes.secret import Secret
from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def kubeconfig_secrets(testconfig, cluster, cluster2, blame, module_label):
    """Creates Opaque secrets containing kubeconfig for the secondary cluster2 on primary cluster"""
    tools2 = cluster2.change_project("tools")
    coredns_sa2 = tools2.get_service_account("coredns")
    kubeconfig2 = coredns_sa2.get_kubeconfig(blame("ctx"), blame("usr"), blame("clstr"), api_url=tools2.api_url)

    return [
        Secret.create_instance(
            cluster.change_project(testconfig["service_protection"]["system_project"]),
            blame("kubecfg"),
            {"kubeconfig": kubeconfig2},
            secret_type="Opaque",
            labels={"app": module_label, "kuadrant.io/multicluster-kubeconfig": "true"},
        )
    ]


@pytest.fixture(scope="package")
def service_monitor(cluster, request, testconfig, blame):
    """Create ServiceMonitor object to follow DNS Operator controller /metrics endpoint"""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])
    endpoints = [MetricsEndpoint("/metrics", "metrics")]
    match_labels = {"control-plane": "dns-operator-controller-manager"}
    monitor = ServiceMonitor.create_instance(system_project, blame("sm"), endpoints, match_labels=match_labels)
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="package", autouse=True)
def wait_for_active_targets(prometheus, service_monitor):
    """Waits for all endpoints in Service Monitor to become active targets"""
    assert prometheus.is_reconciled(service_monitor), "Service Monitor didn't get reconciled in time"
