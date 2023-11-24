"""Tests on mTLS authentication with multiple attributes"""
import pytest

from testsuite.policy.authorization import Pattern


@pytest.fixture(scope="module", autouse=True)
def authorization(authorization, blame, cert_attributes):
    """Add second pattern matching rule to the AuthConfig"""
    rule_country = Pattern("auth.identity.Country", "incl", cert_attributes["C"])
    authorization.authorization.add_auth_rules(blame("redhat"), [rule_country])

    return authorization


def test_mtls_multiple_attributes_success(envoy_authority, valid_cert, hostname):
    """Test successful mtls authentication with two matching attributes"""
    with hostname.client(verify=envoy_authority, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_mtls_multiple_attributes_fail(envoy_authority, custom_cert, hostname):
    """Test mtls authentication with one matched and one unmatched attributes"""
    with hostname.client(verify=envoy_authority, cert=custom_cert) as client:
        response = client.get("/get")
        assert response.status_code == 403
