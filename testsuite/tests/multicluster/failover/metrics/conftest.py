"""Conftest for DNS failover metrics tests"""

import pytest
from dynaconf import ValidationError

from testsuite.httpx import KuadrantClient
from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor
from testsuite.prometheus import Prometheus


@pytest.fixture(scope="module")
def system_project2(cluster2, system_project):
    """Kubernetes client for the system namespace on the second cluster"""
    return cluster2.change_project(system_project.project)


@pytest.fixture(scope="module")
def prometheus2(cluster2, testconfig, skip_or_fail):
    """Prometheus client for the second cluster, discovered using prometheus settings"""
    try:
        testconfig.validators.validate(only=["prometheus"])
        project = testconfig["prometheus"]["project"]
        service_name = testconfig["prometheus"]["service"]
    except (KeyError, ValidationError):
        skip_or_fail("Prometheus not configured. Set prometheus.project and prometheus.service in settings.")
        return

    monitoring = cluster2.change_project(project)
    routes = monitoring.get_routes_for_service(service_name)
    if not routes:
        skip_or_fail(f"Prometheus not available on cluster2: no route for {service_name} in {project}")
        return

    route = routes[0]
    protocol = "https" if "tls" in route.model.spec else "http"
    url = f"{protocol}://{route.model.spec.host}"

    headers = {}
    if url.startswith("https"):
        headers["Authorization"] = f"Bearer {cluster2.token}"

    with KuadrantClient(headers=headers, base_url=url, verify=False) as client:
        yield Prometheus(client)


@pytest.fixture(scope="module")
def service_monitor(system_project, request, blame):
    """ServiceMonitor to scrape DNS Operator controller metrics on cluster1"""
    endpoints = [MetricsEndpoint("/metrics", "metrics")]
    match_labels = {"control-plane": "dns-operator-controller-manager"}
    monitor = ServiceMonitor.create_instance(system_project, blame("sm"), endpoints, match_labels=match_labels)
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="module")
def service_monitor2(system_project2, request, blame):
    """ServiceMonitor to scrape DNS Operator controller metrics on cluster2"""
    endpoints = [MetricsEndpoint("/metrics", "metrics")]
    match_labels = {"control-plane": "dns-operator-controller-manager"}
    monitor = ServiceMonitor.create_instance(system_project2, blame("sm2"), endpoints, match_labels=match_labels)
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="module", autouse=True)
def wait_for_active_targets(prometheus, service_monitor, prometheus2, service_monitor2):
    """Waits for ServiceMonitors to become active targets on both clusters"""
    assert prometheus.is_reconciled(service_monitor), "ServiceMonitor on cluster1 didn't get reconciled"
    assert prometheus2.is_reconciled(service_monitor2), "ServiceMonitor on cluster2 didn't get reconciled"


@pytest.fixture(scope="module")
def dns_record(dns_policy):
    """DNSRecord created by cluster1's DNSPolicy"""
    dns_records = dns_policy.get_dns_records()
    assert len(dns_records) == 1, f"Expected 1 DNSRecord on cluster1, got {len(dns_records)}"
    return dns_records[0]


@pytest.fixture(scope="module")
def dns_record2(dns_policy2):
    """DNSRecord created by cluster2's DNSPolicy"""
    dns_records = dns_policy2.get_dns_records()
    assert len(dns_records) == 1, f"Expected 1 DNSRecord on cluster2, got {len(dns_records)}"
    return dns_records[0]


@pytest.fixture(scope="module")
def dns_metrics(prometheus, service_monitor):
    """All metrics from the DNS Operator on cluster1"""
    prometheus.wait_for_scrape(service_monitor, "/metrics")
    return prometheus.get_metrics(labels={"service": "dns-operator-controller-manager-metrics-service"})


@pytest.fixture(scope="module")
def dns_metrics2(prometheus2, service_monitor2):
    """All metrics from the DNS Operator on cluster2"""
    prometheus2.wait_for_scrape(service_monitor2, "/metrics")
    return prometheus2.get_metrics(labels={"service": "dns-operator-controller-manager-metrics-service"})
