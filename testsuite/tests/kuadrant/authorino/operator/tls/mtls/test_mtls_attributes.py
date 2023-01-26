"""Tests on mTLS authentication with multiple attributes"""
import pytest

from testsuite.objects import Rule


@pytest.fixture(scope="module", autouse=True)
def authorization(authorization, blame, cert_attributes):
    """Add second pattern matching rule to the AuthConfig"""
    rule_country = Rule("auth.identity.Country", "incl", cert_attributes["C"])
    authorization.authorization.auth_rule(blame("redhat"), rule_country)

    return authorization


def test_mtls_multiple_attributes_success(envoy_authority, valid_cert, envoy):
    """Test successful mtls authentication with two matching attributes"""
    with envoy.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_mtls_multiple_attributes_fail(envoy_authority, custom_cert, envoy):
    """Test mtls authentication with one matched and one unmatched attributes"""
    with envoy.client(verify=envoy_authority, cert=custom_cert) as client:
        response = client.get("/get")
        assert response.status_code == 403
