"""Tests that envoy deployed with TLS security works with Authorino"""

import pytest

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


def test_valid_certificate(envoy_authority, valid_cert, auth, hostname):
    """Tests that valid certificate will be accepted"""
    with hostname.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get", auth=auth)
        assert response.status_code == 200


def test_no_certificate(hostname, envoy_authority):
    """Test that request without certificate will be rejected"""
    with hostname.client(verify=envoy_authority) as client:
        result = client.get("/get")
        assert result.has_cert_required_error()


def test_invalid_certificate(envoy_authority, invalid_cert, auth, hostname):
    """Tests that certificate with different CA will be rejeceted"""
    with hostname.client(verify=envoy_authority, cert=invalid_cert) as client:
        result = client.get("/get", auth=auth)
        assert result.has_unknown_ca_error()
