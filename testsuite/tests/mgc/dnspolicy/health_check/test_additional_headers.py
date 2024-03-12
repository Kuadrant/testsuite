"""Tests for DNSPolicy health checks - additional authentication headers sent with health check requests"""

import pytest

from testsuite.openshift.secret import Secret
from testsuite.mockserver import Mockserver
from testsuite.backend.mockserver import MockserverBackend
from testsuite.policy.dns_policy import HealthCheck, AdditionalHeadersRef

pytestmark = [pytest.mark.mgc]

HEADER_NAME = "test-header"
HEADER_VALUE = "test-value"


@pytest.fixture(scope="module")
def backend(request, openshift, blame, label):
    """Use mockserver as backend for health check requests to verify additional headers"""
    mockserver = MockserverBackend(openshift, blame("mocksrv"), label)
    request.addfinalizer(mockserver.delete)
    mockserver.commit()

    return mockserver


@pytest.fixture(scope="module")
def mockserver_client(client):
    """Returns Mockserver client"""
    return Mockserver(str(client.base_url), client=client)


@pytest.fixture(scope="module", autouse=True)
def mockserver_backend_expectation(mockserver_client, module_label):
    """Creates Mockserver Expectation which requires additional headers for successful request"""
    mockserver_client.create_request_expectation(module_label, headers={HEADER_NAME: [HEADER_VALUE]})


@pytest.fixture(scope="module")
def headers_secret(request, hub_openshift, blame):
    """Creates Secret with additional headers for DNSPolicy health check"""
    secret_name = blame("headers")
    headers_secret = Secret.create_instance(hub_openshift, secret_name, {HEADER_NAME: HEADER_VALUE})

    request.addfinalizer(headers_secret.delete)
    headers_secret.commit()
    return secret_name


@pytest.fixture(scope="module")
def health_check(headers_secret, module_label):
    """Returns healthy endpoint specification with additional authentication header for DNSPolicy health check"""
    return HealthCheck(
        allowInsecureCertificates=True,
        additionalHeadersRef=AdditionalHeadersRef(name=headers_secret),
        endpoint=f"/{module_label}",
        interval="5s",
        port=80,
        protocol="http",
    )


def test_additional_headers(dns_health_probe, mockserver_client, module_label):
    """Test if additional headers in health check requests are used"""
    assert dns_health_probe.is_healthy()

    requests = mockserver_client.retrieve_requests(module_label)
    assert len(requests) > 0

    request_headers = requests[0]["headers"]
    assert request_headers.get(HEADER_NAME) == [HEADER_VALUE]
