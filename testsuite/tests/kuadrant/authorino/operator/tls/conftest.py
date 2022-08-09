"""Conftest for all TLS-enabled tests"""
from urllib.parse import urlparse

import pytest

from testsuite.certificates import CFSSLClient, Certificate
from testsuite.openshift.httpbin import TLSEnvoy


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
def wildcard_domain(openshift):
    """
    Hostname of the upstream certificate sent to be validated by APIcast
    May be overwritten to configure different test cases
    """
    hostname = urlparse(openshift.api_url).hostname
    return "*.apps." + hostname.split(".", 1)[1]


@pytest.fixture(scope="session")
def authorino_domain(openshift):
    """
    Hostname of the upstream certificate sent to be validated by APIcast
    May be overwritten to configure different test cases
    """
    return f"*.{openshift.project}.svc.cluster.local"


@pytest.fixture(scope="session")
def envoy_authority(wildcard_domain, cfssl):
    """Authority for all certificates that envoy should accept"""
    return cfssl.create_authority("backend-ca", hosts=[wildcard_domain])


@pytest.fixture(scope="session")
def invalid_authority(wildcard_domain, cfssl):
    """Completely unrelated CA for generating certificates which should not succeed"""
    return cfssl.create_authority("server-ca", hosts=[wildcard_domain])


@pytest.fixture(scope="session")
def authorino_authority(authorino_domain, cfssl):
    """Authority for Authorino Certificate"""
    return cfssl.create_authority("authorino-ca", hosts=[authorino_domain])


@pytest.fixture(scope="session")
def authorino_cert(authorino_domain, cfssl, authorino_authority):
    """Authorino certificate"""
    return cfssl.create("authorino", hosts=[authorino_domain], certificate_authority=authorino_authority)


@pytest.fixture(scope="session")
def envoy_cert(wildcard_domain, cfssl, envoy_authority):
    """Certificate that is actively used by Envoy"""
    return cfssl.create("envoy", hosts=[wildcard_domain], certificate_authority=envoy_authority)


@pytest.fixture(scope="session")
def valid_cert(wildcard_domain, cfssl, envoy_authority):
    """Certificate accepted by Envoy"""
    return cfssl.create("valid", hosts=[wildcard_domain], certificate_authority=envoy_authority)


@pytest.fixture(scope="session")
def invalid_cert(invalid_authority, cfssl, wildcard_domain):
    """Certificate rejected by Envoy"""
    return cfssl.create("invalid", hosts=[wildcard_domain], certificate_authority=invalid_authority)


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, create_secret, blame, label, backend,
          authorino_authority, envoy_authority, envoy_cert):
    """Envoy + Httpbin backend"""
    authorino_secret = create_secret(authorino_authority, "authca")
    envoy_ca_secret = create_secret(envoy_authority, "backendca")
    envoy_secret = create_secret(envoy_cert, "envoycert")

    envoy = TLSEnvoy(openshift, authorino, blame("backend"), label, backend.url,
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
