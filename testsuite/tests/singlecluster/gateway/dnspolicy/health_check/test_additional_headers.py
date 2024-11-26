"""Tests for DNSPolicy health checks - additional authentication headers sent with health check requests"""

import pytest

from testsuite.httpx import KuadrantClient
from testsuite.mockserver import Mockserver
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.dns import HealthCheck, AdditionalHeadersRef
from testsuite.backend.mockserver import MockserverBackend

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]

HEADER_NAME = "test-header"
HEADER_VALUE = "test-value"


@pytest.fixture(scope="module")
def health_check(headers_secret, module_label):
    """Returns healthy endpoint specification with additional authentication header for DNSPolicy health check"""
    return HealthCheck(
        additionalHeadersRef=AdditionalHeadersRef(name=headers_secret),
        path=f"/{module_label}",
        interval="5s",
        protocol="HTTP",
        port=80,
    )


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, base_domain, module_label, subdomain):
    """Create gateway without TLS enabled"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=f"{subdomain}.{base_domain}"))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label):
    """Use mockserver as backend for health check requests to verify additional headers"""
    mockserver = MockserverBackend(cluster, blame("mocksrv"), label)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()
    mockserver.wait_for_ready()
    return mockserver


@pytest.fixture(scope="module")
def headers_secret(request, cluster, blame):
    """Creates Secret with additional headers for DNSPolicy health check"""
    secret_name = blame("headers")
    headers_secret = Secret.create_instance(cluster, secret_name, {HEADER_NAME: HEADER_VALUE})
    request.addfinalizer(headers_secret.delete)
    headers_secret.commit()
    return secret_name


@pytest.fixture(scope="module")
def mockserver_client(backend):
    """Returns Mockserver client from load-balanced service IP"""
    return Mockserver(KuadrantClient(base_url=f"http://{backend.service.refresh().external_ip}: 8080"))


@pytest.fixture(scope="module")
def mockserver_backend_expectation(mockserver_client, module_label):
    """Creates Mockserver Expectation which requires additional headers for successful request"""
    mockserver_client.create_request_expectation(module_label, headers={HEADER_NAME: [HEADER_VALUE]})


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy, mockserver_backend_expectation):  # pylint: disable=unused-argument
    """Commits dnspolicy only"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()
    dns_policy.wait_for_ready()


def test_additional_headers(dns_health_probe, mockserver_client, module_label):
    """Test if additional headers in health check requests are used"""
    assert dns_health_probe.is_healthy()

    requests = mockserver_client.retrieve_requests(module_label)
    assert len(requests) > 0
    assert requests[0]["headers"].get(HEADER_NAME) == [HEADER_VALUE]
