"""mTLS authentication tests"""
import pytest
from httpx import ReadError, ConnectError


def test_mtls_success(envoy_authority, valid_cert, envoy):
    """Test successful mtls authentication"""
    with envoy.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


@pytest.mark.parametrize(
    "cert_authority, certificate, err, err_match",
    [
        pytest.param("envoy_authority", "self_signed_cert", ReadError, "unknown ca", id="Self-Signed Certificate"),
        pytest.param("envoy_authority", "invalid_cert", ReadError, "unknown ca", id="Invalid certificate"),
        pytest.param("envoy_authority", None, ReadError, "certificate required", id="Without certificate"),
        pytest.param(
            "invalid_authority", "valid_cert", ConnectError, "certificate verify failed", id="Unknown authority"
        ),
    ],
)
def test_mtls_fail(request, cert_authority, certificate, err, err_match: str, envoy):
    """Test failed mtls verification"""
    ca = request.getfixturevalue(cert_authority)
    cert = request.getfixturevalue(certificate) if certificate else None

    with pytest.raises(err, match=err_match):
        with envoy.client(verify=ca, cert=cert) as client:
            client.get("/get")


def test_mtls_unmatched_attributes(envoy_authority, custom_cert, envoy):
    """Test certificate that signed by the trusted CA, though their attributes are unmatched"""
    with envoy.client(verify=envoy_authority, cert=custom_cert) as client:
        response = client.get("/get")
        assert response.status_code == 403
