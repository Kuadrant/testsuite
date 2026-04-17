"""Tests for x509 client certificate authentication using Gateway API v1.5+ frontend TLS validation.
Tier 1 from RFC 0015 - https://github.com/Kuadrant/architecture/blob/main/rfcs/0015-x509-client-cert-authpolicy.md

Client certificate validation is configured at the gateway level using the standard Gateway API
spec.tls.frontend.default.validation configuration. The gateway validates client certificates
at L4 (TLS layer) and populates the XFCC header for Authorino to extract and validate
the certificate via x509 identity in AuthPolicy.
"""

import pytest

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.gateway_api_version((1, 5, 0))]


def test_valid_cert(hostname, server_ca, valid_cert):
    """Test that a request with a valid client certificate succeeds"""
    with hostname.client(verify=server_ca, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_no_cert(hostname, server_ca):
    """
    Test that a request without a client certificate is rejected at the gateway level (L4),
    where certificate validation is happening due to the Gateway API frontend TLS validation configuration
    """
    with hostname.client(verify=server_ca) as client:
        response = client.get("/get")
        assert response.has_cert_required_error()


def test_invalid_cert(hostname, server_ca, invalid_cert):
    """
    Test that a request with a certificate signed by an untrusted CA is rejected at the gateway level (L4),
    where certificate validation is happening due to the Gateway API frontend TLS validation configuration
    """
    with hostname.client(verify=server_ca, cert=invalid_cert) as client:
        response = client.get("/get")
        assert response.has_unknown_ca_error()
