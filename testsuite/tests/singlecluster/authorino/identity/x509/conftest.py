"""Conftest for x509 client certificate authentication tests"""

import pytest

from testsuite.certificates import CertInfo
from testsuite.utils import cert_builder
from testsuite.kubernetes import Selector
from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.authorization import X509Source

XFCC_HEADER_NAME = "x-forwarded-client-cert"


@pytest.fixture(scope="session")
def cert_attributes():
    """Certificate attributes for client certificates"""
    return {
        "O": "Organization Test",
        "OU": "Unit Test",
        "L": "Location Test",
        "ST": "State Test",
        "C": "Country Test",
    }


@pytest.fixture(scope="module")
def certificates(cfssl, wildcard_domain, cert_attributes):
    """Certificate hierarchy used for x509 tests"""
    chain = {
        "client_ca": CertInfo(
            children={
                "valid_cert": CertInfo(names=[cert_attributes]),
            }
        ),
        "invalid_ca": CertInfo(children={"invalid_cert": None}),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def client_ca(certificates):
    """CA certificate used for client certificate validation"""
    return certificates["client_ca"]


@pytest.fixture(scope="module")
def valid_cert(certificates):
    """Valid client certificate signed by the trusted CA"""
    return certificates["valid_cert"]


@pytest.fixture(scope="module")
def invalid_cert(certificates):
    """Client certificate signed by an untrusted CA"""
    return certificates["invalid_cert"]


@pytest.fixture(scope="module")
def certificate_selector_labels(blame):
    """Labels for Selector to select the AuthPolicy for x509 tests"""
    return {"cert-selector": blame("x509")}


@pytest.fixture(scope="module")
def client_ca_secret(request, cluster, blame, client_ca, certificate_selector_labels):
    """Create Kubernetes Secret with client CA certificate, with labels matching the selector in AuthPolicy"""
    secret = Secret.create_instance(
        cluster, blame("client-ca"), stringData={"ca.crt": client_ca.certificate}, labels=certificate_selector_labels
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def authorization(authorization, certificate_selector_labels):
    """AuthPolicy with x509 identity configured, matching certificates secrets selected by the label"""
    authorization.identity.add_mtls(
        "x509", Selector(matchLabels=certificate_selector_labels), source=X509Source(xfcc=XFCC_HEADER_NAME)
    )
    return authorization
