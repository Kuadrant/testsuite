"""Conftest for all TLS-enabled tests"""
from typing import Optional, Dict

import pytest

from testsuite.certificates import CFSSLClient, Certificate, CertInfo
from testsuite.openshift.envoy import TLSEnvoy
from testsuite.utils import cert_builder


@pytest.fixture(scope="session")
def cert_attributes() -> Dict[str, str]:
    """Certificate attributes"""
    return dict(O="Organization Test", OU="Unit Test", L="Location Test", ST="State Test", C="Country Test")


@pytest.fixture(scope="session")
def cert_attributes_other(cert_attributes) -> Dict[str, str]:
    """Certificate attributes that are different from the default ones"""
    return {k: f"{v}-other" for k, v in cert_attributes.items()}


@pytest.fixture(scope="session")
def certificates(cfssl, authorino_domain, wildcard_domain, cert_attributes, cert_attributes_other):
    """Certificate hierarchy used for the tests"""
    chain = {
        "envoy_ca":
        CertInfo(
            children={
                "envoy_cert": None,
                "valid_cert": CertInfo(names=[cert_attributes]),
                "custom_cert": CertInfo(names=[cert_attributes_other])
            }),
        "authorino_ca":
        CertInfo(children={
            "authorino_cert": CertInfo(hosts=authorino_domain),
        }),
        "invalid_ca":
        CertInfo(children={"invalid_cert": None})
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="session")
def create_secret(blame, request, openshift):
    """Creates TLS secret from Certificate"""

    def _create_secret(certificate: Certificate, name: str, labels: Optional[Dict[str, str]] = None):
        secret_name = blame(name)
        secret = openshift.create_tls_secret(secret_name, certificate, labels=labels)
        request.addfinalizer(lambda: openshift.delete_selector(secret))
        return secret_name

    return _create_secret


@pytest.fixture(scope="session")
def cfssl(testconfig):
    """CFSSL client library"""
    client = CFSSLClient(binary=testconfig["cfssl"])
    if not client.exists:
        pytest.skip("Skipping CFSSL tests as CFSSL binary path is not properly configured")
    return client


@pytest.fixture(scope="session")
def authorino_domain(openshift):
    """
    Hostname of the upstream certificate sent to be validated by APIcast
    May be overwritten to configure different test cases
    """
    return f"*.{openshift.project}.svc.cluster.local"


@pytest.fixture(scope="session")
def envoy_authority(certificates):
    """Authority for all certificates that envoy should accept"""
    return certificates["envoy_ca"]


@pytest.fixture(scope="session")
def invalid_authority(certificates):
    """Completely unrelated CA for generating certificates which should not succeed"""
    return certificates["invalid_ca"]


@pytest.fixture(scope="session")
def authorino_authority(certificates):
    """Authority for Authorino Certificate"""
    return certificates["authorino_ca"]


@pytest.fixture(scope="session")
def authorino_cert(certificates):
    """Authorino certificate"""
    return certificates["authorino_cert"]


@pytest.fixture(scope="session")
def envoy_cert(certificates):
    """Certificate that is actively used by Envoy"""
    return certificates["envoy_cert"]


@pytest.fixture(scope="session")
def valid_cert(certificates):
    """Certificate accepted by Envoy"""
    return certificates["valid_cert"]


@pytest.fixture(scope="session")
def custom_cert(certificates):
    """Envoy certificate that have different attributes"""
    return certificates["custom_cert"]


@pytest.fixture(scope="session")
def invalid_cert(certificates):
    """Certificate rejected by Envoy"""
    return certificates["invalid_cert"]


@pytest.fixture(scope="module")
def selector_params(module_label):
    """Label key-value pair for the CA secret discovery"""
    return "testLabel", module_label


@pytest.fixture(scope="module")
def authorino_labels(selector_params) -> Dict[str, str]:
    """Labels for the proper Authorino discovery"""
    labels = {"authorino.kuadrant.io/managed-by": "authorino", selector_params[0]: selector_params[1]}
    return labels


# pylint: disable-msg=too-many-locals
@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, create_secret, blame, label, backend, authorino_authority, envoy_authority,
          envoy_cert, testconfig, authorino_labels):
    """Envoy + Httpbin backend"""
    authorino_secret = create_secret(authorino_authority, "authca")
    envoy_ca_secret = create_secret(envoy_authority, "backendca", labels=authorino_labels)
    envoy_secret = create_secret(envoy_cert, "envoycert")

    envoy = TLSEnvoy(openshift, authorino, blame("backend"), label, backend.url, testconfig["envoy"]["image"],
                     authorino_secret, envoy_ca_secret, envoy_secret)
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters, authorino_cert, create_secret):
    """Setup TLS for authorino"""
    authorino_secret_name = create_secret(authorino_cert, "authcert")
    authorino_parameters["listener_certificate_secret"] = authorino_secret_name
    yield authorino_parameters
