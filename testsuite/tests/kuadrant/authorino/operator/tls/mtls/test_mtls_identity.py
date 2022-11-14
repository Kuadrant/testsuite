"""mTLS authentication tests"""
import pytest
from httpx import ReadError, ConnectError

from testsuite.objects import Rule


@pytest.fixture(scope="module", autouse=True)
def authorization(authorization, blame, selector_params, cert_attributes):
    """Create AuthConfig with mtls identity and pattern matching rule"""
    authorization.identity.remove_all()

    authorization.identity.mtls(blame("mtls"), *selector_params)
    rule = Rule("auth.identity.Organization", "incl", cert_attributes["O"])
    authorization.authorization.auth_rule(blame("redhat"), rule)
    return authorization


def test_mtls_success(envoy_authority, valid_cert, envoy):
    """Test successful mtls authentication"""
    with envoy.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


@pytest.mark.parametrize("cert_authority, certificate, err, err_match", [
    pytest.param("envoy_authority", "invalid_cert", ReadError, "unknown ca", id="Invalid certificate"),
    pytest.param("invalid_authority", "valid_cert", ConnectError, "certificate verify failed", id="Unknown authority"),
])
def test_mtls_fail(request, cert_authority, certificate, err, err_match: str, envoy):
    """Test mtls verification with invalid certificate or unknown signed authority"""
    ca = request.getfixturevalue(cert_authority)
    cert = request.getfixturevalue(certificate)

    with pytest.raises(err, match=err_match):
        with envoy.client(verify=ca, cert=cert) as client:
            client.get("/get")


def test_mtls_unmatched_attributes(envoy_authority, custom_cert, envoy):
    """Test certificate that signed by the trusted CA, though their attributes are unmatched"""
    with envoy.client(verify=envoy_authority, cert=custom_cert) as client:
        response = client.get("/get")
        assert response.status_code == 403
