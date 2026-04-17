"""Test x509 client certificate authentication with CEL expression on AuthConfig"""

import pytest

from testsuite.kuadrant.policy.authorization import X509Source

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module", autouse=True)
def authorization(authorization, blame, selector):
    """AuthConfig with x509 identity using CEL expression for certificate source"""
    authorization.identity.add_mtls(
        blame("x509"), selector=selector, source=X509Source(expression="source.certificate")
    )
    return authorization


def test_x509_success(envoy_authority, valid_cert, hostname):
    """Test successful x509 authentication with CEL expression"""
    with hostname.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_x509_invalid_cert(envoy_authority, invalid_cert, hostname):
    """Test that a certificate signed by an untrusted CA is rejected"""
    with hostname.client(verify=envoy_authority, cert=invalid_cert) as client:
        result = client.get("/get")
        assert result.has_unknown_ca_error()


def test_x509_no_cert(envoy_authority, hostname):
    """Test that a request without a client certificate is rejected"""
    with hostname.client(verify=envoy_authority) as client:
        result = client.get("/get")
        assert result.has_cert_required_error()
