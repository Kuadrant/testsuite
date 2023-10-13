"""Conftest for the Authorino metrics tests"""
import pytest

from testsuite.openshift.objects.metrics import ServiceMonitor, MetricsEndpoint, Prometheus


@pytest.fixture(scope="module")
def run_on_kuadrant():
    """Kuadrant doesn't allow customization of Authorino parameters"""
    return False


@pytest.fixture(scope="session")
def prometheus(request, openshift):
    """
    Return an instance of OpenShift metrics client
    Skip tests if query route is not properly configured
    """
    # find thanos-querier route in the openshift-monitoring project
    # this route allows to query metrics
    openshift_monitoring = openshift.change_project("openshift-monitoring")
    routes = openshift_monitoring.get_routes_for_service("thanos-querier")
    if len(routes) > 0:
        url = ("https://" if "tls" in routes[0].model.spec else "http://") + routes[0].model.spec.host
        prometheus = Prometheus(url, openshift.token, openshift.project)
        request.addfinalizer(prometheus.close)
        return prometheus

    return pytest.skip("Skipping metrics tests as query route is not properly configured")


@pytest.fixture(scope="module")
def label_metrics_service(authorino, module_label):
    """Label Authorino controller-metrics service for the proper discovery"""
    authorino.metrics_service.label({"app": module_label})


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def create_service_monitor(openshift, blame, module_label, label_metrics_service):
    """Create ServiceMonitor object to follow Authorino /metrics and /server-metrics endpoints"""
    endpoints = [MetricsEndpoint("/metrics", "http"), MetricsEndpoint("/server-metrics", "http")]
    service_monitor = ServiceMonitor.create_instance(
        openshift, blame("sm"), endpoints, match_labels={"app": module_label}
    )

    service_monitor.commit()
    yield service_monitor
    service_monitor.delete()


@pytest.fixture(scope="module", autouse=True)
def send_request(client, auth):
    """Send a simple get request so that a few metrics can appear"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
