"""Conftest for all TLS-enabled tests"""
from typing import Dict

import pytest

from testsuite.certificates import CFSSLClient, Certificate, CertInfo
from testsuite.openshift.envoy import TLSEnvoy
from testsuite.utils import cert_builder


@pytest.fixture(scope="session")
def cert_attributes() -> Dict[str, str]:
    """Certificate attributes"""
    return dict(O="Red Hat Inc.",
                OU="IT",
                L="San Francisco",
                ST="California",
                C="US",)


@pytest.fixture(scope="session")
def certificates(cfssl, authorino_domain, wildcard_domain, cert_attributes):
    """Certificate hierarchy used for the tests"""
    chain = {
        "envoy_ca": CertInfo(names=[cert_attributes], children={
            "envoy_cert": None,
            "valid_cert": CertInfo(names=[cert_attributes])
        }),
        "authorino_ca": CertInfo(children={
            "authorino_cert": CertInfo(hosts=authorino_domain),
        }),
        "invalid_ca": CertInfo(children={
            "invalid_cert": None
        })
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="session")
def create_secret(blame, request, openshift):
    """Creates TLS secret from Certificate"""
    def _create_secret(certificate: Certificate, name):
        secret_name = blame(name)
        secret = openshift.create_tls_secret(secret_name, certificate)
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
def invalid_cert(invalid_authority, cfssl, wildcard_domain):
    """Certificate rejected by Envoy"""
    return cfssl.create("invalid", hosts=[wildcard_domain], certificate_authority=invalid_authority)


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, create_secret, blame, label, backend,
          authorino_authority, envoy_authority, envoy_cert, testconfig):
    """Envoy + Httpbin backend"""
    authorino_secret = create_secret(authorino_authority, "authca")
    envoy_ca_secret = create_secret(envoy_authority, "backendca")
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
