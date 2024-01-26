"""mTLS authentication tests"""

from typing import Callable
import pytest

from testsuite.httpx import Result


def test_mtls_success(envoy_authority, valid_cert, hostname):
    """Test successful mtls authentication"""
    with hostname.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


@pytest.mark.parametrize(
    "cert_authority, certificate, check_error",
    [
        pytest.param("envoy_authority", "self_signed_cert", Result.has_unknown_ca_error, id="Self-signed cert"),
        pytest.param("envoy_authority", "invalid_cert", Result.has_unknown_ca_error, id="Invalid certificate"),
        pytest.param("envoy_authority", None, Result.has_cert_required_error, id="Without certificate"),
        pytest.param("invalid_authority", "valid_cert", Result.has_cert_verify_error, id="Unknown authority"),
    ],
)
def test_mtls_fail(request, cert_authority, certificate, check_error: Callable, hostname):
    """Test failed mtls verification"""
    ca = request.getfixturevalue(cert_authority)
    cert = request.getfixturevalue(certificate) if certificate else None

    with hostname.client(verify=ca, cert=cert) as client:
        result = client.get("/get")
        assert check_error(result)


def test_mtls_unmatched_attributes(envoy_authority, custom_cert, hostname):
    """Test certificate that signed by the trusted CA, though their attributes are unmatched"""
    with hostname.client(verify=envoy_authority, cert=custom_cert) as client:
        response = client.get("/get")
        assert response.status_code == 403
