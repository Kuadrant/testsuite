"""Tests for x509 client certificate authentication using RFC 9440 Client-Cert header.
https://github.com/Kuadrant/testsuite/issues/900

L7-only validation where the gateway does NOT validate client certificates at the TLS level.
Instead, the client sends the certificate in the Client-Cert header (base64-encoded DER format),
and Authorino extracts and validates it using x509 identity with clientCertHeader source.
"""

import pytest

from testsuite.kubernetes import Selector
from testsuite.kuadrant.policy.authorization import X509Source

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]

CLIENT_CERT_HEADER_NAME = "Client-Cert"


@pytest.fixture(scope="module")
def authorization(authorization, certificate_selector_labels, client_ca_secret):  # pylint: disable=unused-argument
    """AuthPolicy with x509 identity configured to read from Client-Cert header"""
    authorization.identity.clear_all()
    authorization.identity.add_mtls(
        "x509",
        Selector(matchLabels=certificate_selector_labels),
        source=X509Source(clientCertHeader=CLIENT_CERT_HEADER_NAME),
    )
    return authorization


def test_valid_cert(client, valid_cert):
    """Test that a request with a valid client certificate in Client-Cert header succeeds"""
    response = client.get("/get", headers={CLIENT_CERT_HEADER_NAME: valid_cert.client_cert_header})
    assert response.status_code == 200


def test_no_header(client):
    """Test that a request without Client-Cert header is rejected by Authorino (L7)"""
    response = client.get("/get")
    assert not response.has_cert_required_error()
    assert response.status_code == 401


def test_invalid_cert(client, invalid_cert):
    """Test that an invalid certificate in Client-Cert header is rejected by Authorino (L7)"""
    response = client.get("/get", headers={CLIENT_CERT_HEADER_NAME: invalid_cert.client_cert_header})
    assert not response.has_unknown_ca_error()
    assert response.status_code == 401
