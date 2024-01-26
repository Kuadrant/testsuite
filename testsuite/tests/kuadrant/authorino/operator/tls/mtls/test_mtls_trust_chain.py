"""mTLS trust chain tests"""

import pytest


@pytest.fixture(scope="module", autouse=True)
def create_intermediate_authority_secrets(create_secret, authorino_labels, certificates):
    """Create Intermediate Certification Authority (CA) tls secrets"""
    create_secret(certificates["intermediate_ca"], "interca", labels=authorino_labels)
    create_secret(certificates["intermediate_ca_unlabeled"], "interunld")


def test_mtls_trust_chain_success(envoy_authority, certificates, hostname):
    """Test mtls verification with certificate signed by intermediate authority in the trust chain"""
    with hostname.client(verify=envoy_authority, cert=certificates["intermediate_valid_cert"]) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_mtls_trust_chain_fail(envoy_authority, certificates, hostname):
    """Test mtls verification on intermediate certificate with unmatched attribute"""
    with hostname.client(verify=envoy_authority, cert=certificates["intermediate_custom_cert"]) as client:
        response = client.get("/get")
        assert response.status_code == 403


def test_mtls_trust_chain_rejected_cert(envoy_authority, certificates, hostname):
    """Test mtls verification with intermediate certificate accepted in Envoy, but rejected by Authorino"""
    with hostname.client(verify=envoy_authority, cert=certificates["intermediate_cert_unlabeled"]) as client:
        response = client.get("/get")
        assert response.status_code == 401
