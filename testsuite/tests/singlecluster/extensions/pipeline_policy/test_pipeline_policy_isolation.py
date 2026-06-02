"""Tests for PipelinePolicy isolation: policy should not leak to untargeted routes or gateways."""

import time

import pytest

from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.utils.constants import EXTENSION_POLICY_PROPAGATION_WAIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def hostname2(gateway, exposer, blame):
    """Second hostname for the unaffected route on the same gateway"""
    return exposer.expose_hostname(blame("no-pp"), gateway)


@pytest.fixture(scope="module")
def route2(request, gateway, blame, hostname2, backend, module_label):
    """Second HTTPRoute on the same gateway without any PipelinePolicy"""
    route = HTTPRoute.create_instance(gateway.cluster, blame("route2"), gateway, {"app": module_label})
    route.add_hostname(hostname2.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def client2(route2, hostname2):  # pylint: disable=unused-argument
    """Client for the route without PipelinePolicy"""
    client = hostname2.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def gateway2(request, cluster, blame, wildcard_domain, module_label):
    """Second gateway without any PipelinePolicy"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw2"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname3(gateway2, exposer, blame):
    """Hostname for the route on the second gateway"""
    return exposer.expose_hostname(blame("no-pp-gw"), gateway2)


@pytest.fixture(scope="module")
def route3(request, gateway2, blame, hostname3, backend, module_label):
    """HTTPRoute on the second gateway without any PipelinePolicy"""
    route = HTTPRoute.create_instance(gateway2.cluster, blame("route3"), gateway2, {"app": module_label})
    route.add_hostname(hostname3.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def client3(route3, hostname3):  # pylint: disable=unused-argument
    """Client for the route on the second gateway"""
    client = hostname3.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with response header targeting only the first route."""
    pipeline_policy.on_http_response.add_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


def test_policy_affects_targeted_route(client):
    """Route with PipelinePolicy gets the response header."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2023")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/kuadrant-operator/issues/2023")
def test_policy_does_not_affect_other_route(client2):
    """Route without PipelinePolicy on the same gateway does not get the response header."""
    time.sleep(EXTENSION_POLICY_PROPAGATION_WAIT)
    response = client2.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") is None


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2023")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/kuadrant-operator/issues/2023")
def test_policy_does_not_affect_other_gateway(client3):
    """Route on a different gateway does not get the response header."""
    time.sleep(EXTENSION_POLICY_PROPAGATION_WAIT)
    response = client3.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") is None
