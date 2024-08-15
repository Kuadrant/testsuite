"""Conftest for the Authorino metrics tests"""

import pytest
import yaml
from openshift_client import selector

from testsuite.httpx import KuadrantClient
from testsuite.kubernetes.config_map import ConfigMap
from testsuite.kubernetes.service_monitor import ServiceMonitor, MetricsEndpoint
from testsuite.prometheus import Prometheus


@pytest.fixture(scope="package")
def prometheus(cluster):
    """
    Return an instance of Thanos metrics client
    Skip tests if query route is not properly configured
    """
    openshift_monitoring = cluster.change_project("openshift-monitoring")
    # Check if metrics are enabled
    try:
        with openshift_monitoring.context:
            cm = selector("cm/cluster-monitoring-config").object(cls=ConfigMap)
            assert yaml.safe_load(cm["config.yaml"])["enableUserWorkload"]
    except Exception:  # pylint: disable=broad-exception-caught
        pytest.skip("User workload monitoring is disabled")

    # find thanos-querier route in the openshift-monitoring project
    # this route allows to query metrics

    routes = openshift_monitoring.get_routes_for_service("thanos-querier")
    if len(routes) == 0:
        pytest.skip("Skipping metrics tests as query route is not properly configured")

    url = ("https://" if "tls" in routes[0].model.spec else "http://") + routes[0].model.spec.host
    with KuadrantClient(headers={"Authorization": f"Bearer {cluster.token}"}, base_url=url, verify=False) as client:
        yield Prometheus(client)


@pytest.fixture(scope="package")
def service_monitor(cluster, request, blame, authorino):
    """Create ServiceMonitor object to follow Authorino /metrics and /server-metrics endpoints"""
    label = {"app": authorino.name() + "metrics"}
    authorino.metrics_service.label(label)
    endpoints = [MetricsEndpoint("/metrics", "http"), MetricsEndpoint("/server-metrics", "http")]
    monitor = ServiceMonitor.create_instance(
        cluster.change_project(authorino.namespace()), blame("sm"), endpoints, match_labels=label
    )
    request.addfinalizer(monitor.delete)
    monitor.commit()
    return monitor


@pytest.fixture(scope="package", autouse=True)
def wait_for_active_targets(prometheus, service_monitor):
    """Waits for all endpoints in Service Monitor to become active targets"""
    assert prometheus.is_reconciled(service_monitor), "Service Monitor didn't get reconciled in time"
