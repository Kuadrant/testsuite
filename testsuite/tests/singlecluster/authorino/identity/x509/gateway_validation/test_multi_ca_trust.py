"""Tests for x509 multi-CA trust via label selectors.

Verifies that AuthPolicy can trust multiple intermediate CAs independently via label selectors.
The gateway trusts a root CA at L4 (all certs pass TLS), while Authorino selects
trusted CA secrets by label, providing fine-grained L7 trust control.
"""

import time

import pytest

from testsuite.certificates import CertInfo
from testsuite.utils import cert_builder
from testsuite.kubernetes import Selector
from testsuite.kuadrant.policy.authorization import X509Source
from ..conftest import XFCC_HEADER_NAME

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.gateway_api_version((1, 5, 0))]


@pytest.fixture(scope="module")
def certificates(cfssl, wildcard_domain, cert_attributes):
    """Certificate hierarchy: root CA with three intermediate CAs, each signing a client certificate"""
    chain = {
        "root_ca": CertInfo(
            children={
                "ca_team_a": CertInfo(children={"cert_team_a": CertInfo(names=[cert_attributes])}),
                "ca_team_b": CertInfo(children={"cert_team_b": CertInfo(names=[cert_attributes])}),
                "ca_untrusted": CertInfo(children={"cert_untrusted": CertInfo(names=[cert_attributes])}),
            }
        ),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def client_ca(certificates):
    """Root CA for gateway-level TLS validation, trusting all intermediate CAs"""
    return certificates["root_ca"]


@pytest.fixture(scope="module")
def cert_team_a(certificates):
    """Client certificate signed by trusted intermediate CA team A"""
    return certificates["cert_team_a"]


@pytest.fixture(scope="module")
def cert_team_b(certificates):
    """Client certificate signed by trusted intermediate CA team B"""
    return certificates["cert_team_b"]


@pytest.fixture(scope="module")
def cert_untrusted(certificates):
    """Client certificate signed by untrusted intermediate CA"""
    return certificates["cert_untrusted"]


@pytest.fixture(scope="module")
def certificate_selector_labels(blame):
    """Labels for Selector to match trusted CA secrets"""
    return {"cert-selector": blame("multi-ca")}


@pytest.fixture(scope="module")
def ca_secret_team_a(create_secret, certificates, certificate_selector_labels):
    """Intermediate CA team A secret in system namespace with matching labels"""
    return create_secret(
        "ca-team-a", {"ca.crt": certificates["ca_team_a"].certificate}, labels=certificate_selector_labels
    )


@pytest.fixture(scope="module")
def ca_secret_team_b(create_secret, certificates, certificate_selector_labels):
    """Intermediate CA team B secret in system namespace with matching labels"""
    return create_secret(
        "ca-team-b", {"ca.crt": certificates["ca_team_b"].certificate}, labels=certificate_selector_labels
    )


@pytest.fixture(scope="module")
def authorization(authorization, certificate_selector_labels):
    """AuthPolicy with x509 identity selecting multiple CA secrets by label"""
    authorization.identity.clear_all()
    authorization.identity.add_mtls(
        "x509",
        Selector(matchLabels=certificate_selector_labels),
        source=X509Source(xfccHeader=XFCC_HEADER_NAME),
    )
    return authorization


@pytest.fixture(scope="module", autouse=True)
def commit(request, tls_policy, authorization, ca_secret_team_a, ca_secret_team_b):  # pylint: disable=unused-argument
    """Commits TLSPolicy and AuthPolicy with delay for WasmPlugin sync"""
    for component in [tls_policy, authorization]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
    time.sleep(15)  # Kind workaround before https://github.com/envoyproxy/envoy/pull/43928 is released in istio 1.30


def test_multi_ca_trust(hostname, server_ca, cert_team_a, cert_team_b, cert_untrusted):
    """Test that certificates from labeled CAs succeed and unlabeled CA is rejected at L7"""
    with hostname.client(verify=server_ca, cert=cert_team_a) as client:
        response = client.get("/get")
        assert response.status_code == 200

    with hostname.client(verify=server_ca, cert=cert_team_b) as client:
        response = client.get("/get")
        assert response.status_code == 200

    with hostname.client(verify=server_ca, cert=cert_untrusted) as client:
        response = client.get("/get")
        assert response.status_code == 401
