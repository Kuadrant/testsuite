"""Conftest for all TLS-enabled tests"""

from typing import Optional, Dict

import pytest

from testsuite.certificates import Certificate, CertInfo
from testsuite.openshift import Selector
from testsuite.gateway import Exposer
from testsuite.gateway.envoy.tls import TLSEnvoy
from testsuite.gateway.exposers import OpenShiftExposer, KindExposer
from testsuite.openshift.secret import TLSSecret
from testsuite.utils import cert_builder


@pytest.fixture(scope="session")
def cert_attributes() -> Dict[str, str]:
    """Certificate attributes"""
    return {
        "O": "Organization Test",
        "OU": "Unit Test",
        "L": "Location Test",
        "ST": "State Test",
        "C": "Country Test",
    }


@pytest.fixture(scope="session")
def cert_attributes_other(cert_attributes) -> Dict[str, str]:
    """Certificate attributes that are partially different from the default ones"""
    return {
        "O": "Other Organization",
        "OU": "Other Unit",
        "L": cert_attributes["L"],
        "ST": cert_attributes["ST"],
        "C": cert_attributes["C"],
    }


@pytest.fixture(scope="module")
def certificates(cfssl, authorino_domain, wildcard_domain, cert_attributes, cert_attributes_other):
    """
    Certificate hierarchy used for the tests
    May be overwritten to configure different test cases
    """
    chain = {
        "envoy_ca": CertInfo(
            children={
                "envoy_cert": None,
                "valid_cert": CertInfo(names=[cert_attributes]),
                "custom_cert": CertInfo(names=[cert_attributes_other]),
            }
        ),
        "authorino_ca": CertInfo(
            children={
                "authorino_cert": CertInfo(hosts=authorino_domain),
            }
        ),
        "invalid_ca": CertInfo(children={"invalid_cert": None}),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def create_secret(blame, request, openshift):
    """Creates TLS secret from Certificate"""

    def _create_secret(certificate: Certificate, name: str, labels: Optional[Dict[str, str]] = None):
        secret_name = blame(name)
        secret = TLSSecret.create_instance(openshift, secret_name, certificate, labels=labels)
        request.addfinalizer(secret.delete)
        secret.commit()
        return secret_name

    return _create_secret


@pytest.fixture(scope="module")
def authorino_domain(openshift):
    """
    Hostname of the upstream certificate sent to be validated by Envoy
    May be overwritten to configure different test cases
    """
    return f"*.{openshift.project}.svc.cluster.local"


@pytest.fixture(scope="module")
def envoy_authority(certificates):
    """Authority for all certificates that envoy should accept"""
    return certificates["envoy_ca"]


@pytest.fixture(scope="module")
def invalid_authority(certificates):
    """Completely unrelated CA for generating certificates which should not succeed"""
    return certificates["invalid_ca"]


@pytest.fixture(scope="module")
def authorino_authority(certificates):
    """Authority for Authorino Certificate"""
    return certificates["authorino_ca"]


@pytest.fixture(scope="module")
def authorino_cert(certificates):
    """Authorino certificate"""
    return certificates["authorino_cert"]


@pytest.fixture(scope="module")
def envoy_cert(certificates):
    """Certificate that is actively used by Envoy"""
    return certificates["envoy_cert"]


@pytest.fixture(scope="module")
def valid_cert(certificates):
    """Certificate accepted by Envoy"""
    return certificates["valid_cert"]


@pytest.fixture(scope="module")
def custom_cert(certificates):
    """Envoy certificate that have different attributes"""
    return certificates["custom_cert"]


@pytest.fixture(scope="module")
def invalid_cert(certificates):
    """Certificate rejected by Envoy"""
    return certificates["invalid_cert"]


@pytest.fixture(scope="module")
def selector(module_label):
    """Label key-value pair for the CA secret discovery"""
    return Selector(matchLabels={"testLabel": module_label})


@pytest.fixture(scope="module")
def authorino_labels(selector) -> Dict[str, str]:
    """Labels for the proper Authorino discovery"""
    labels = {"authorino.kuadrant.io/managed-by": "authorino", **selector.matchLabels}
    return labels


# pylint: disable-msg=too-many-locals
@pytest.fixture(scope="module")
def gateway(
    request,
    authorino,
    openshift,
    create_secret,
    blame,
    module_label,
    authorino_authority,
    envoy_authority,
    envoy_cert,
    testconfig,
    authorino_labels,
):
    """Envoy + Httpbin backend"""
    authorino_secret = create_secret(authorino_authority, "authca")
    envoy_ca_secret = create_secret(envoy_authority, "backendca", labels=authorino_labels)
    envoy_secret = create_secret(envoy_cert, "envoycert")

    envoy = TLSEnvoy(
        openshift,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        authorino_secret,
        envoy_ca_secret,
        envoy_secret,
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="session")
def exposer(exposer) -> Exposer:
    """Exposer object instance with TLS passthrough"""
    if isinstance(exposer, KindExposer):
        pytest.skip("TLS tests dont work with Kind")
    exposer.passthrough = True
    return exposer


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters, authorino_cert, create_secret):
    """Setup TLS for authorino"""
    authorino_secret_name = create_secret(authorino_cert, "authcert")
    authorino_parameters["listener_certificate_secret"] = authorino_secret_name
    return authorino_parameters
