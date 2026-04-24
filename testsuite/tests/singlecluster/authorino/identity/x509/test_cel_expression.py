"""Tests for x509 client certificate authentication using CEL expression source.

L7-only validation where the gateway does NOT validate client certificates at the TLS level.
The client sends the URL-encoded PEM certificate in a custom header, and Authorino extracts it
using a CEL expression pointing to that header via x509 identity with expression source.
"""

import pytest

from testsuite.kubernetes import Selector
from testsuite.kuadrant.policy.authorization import X509Source

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]

CERT_HEADER_NAME = "pem-encoded-client-cert"


@pytest.fixture(scope="module")
def authorization(authorization, certificate_selector_labels, client_ca_secret):  # pylint: disable=unused-argument
    """AuthPolicy with x509 identity configured to extract certificate via CEL expression"""
    authorization.identity.clear_all()
    authorization.identity.add_mtls(
        "x509",
        Selector(matchLabels=certificate_selector_labels),
        source=X509Source(expression=f'request.headers["{CERT_HEADER_NAME}"]'),
    )
    return authorization


def test_valid_cert(client, valid_cert):
    """Test that a request with a valid URL-encoded PEM certificate in header specified by CEL succeeds"""
    response = client.get("/get", headers={CERT_HEADER_NAME: valid_cert.url_encoded_pem})
    assert response.status_code == 200


def test_no_header(client):
    """Test that a request without the certificate header specified by CEL is rejected by Authorino (L7)"""
    response = client.get("/get")
    assert not response.has_cert_required_error()
    assert response.status_code == 401


def test_invalid_cert(client, invalid_cert):
    """Test that an invalid certificate in header specified by CEL is rejected by Authorino (L7)"""
    response = client.get("/get", headers={CERT_HEADER_NAME: invalid_cert.url_encoded_pem})
    assert not response.has_unknown_ca_error()
    assert response.status_code == 401
