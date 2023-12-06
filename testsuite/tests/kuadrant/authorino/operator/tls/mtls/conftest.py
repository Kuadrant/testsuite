"""Conftest for all mTLS tests"""
import pytest

from testsuite.certificates import CertInfo
from testsuite.utils import cert_builder
from testsuite.policy.authorization import Rule


@pytest.fixture(scope="module", autouse=True)
def authorization(authorization, blame, selector, cert_attributes):
    """Create AuthConfig with mtls identity and pattern matching rule"""
    authorization.identity.add_mtls(blame("mtls"), selector=selector)

    rule_organization = Rule("auth.identity.Organization", "incl", cert_attributes["O"])
    authorization.authorization.add_auth_rules(blame("redhat"), [rule_organization])

    return authorization


@pytest.fixture(scope="module")
def certificates(cfssl, authorino_domain, wildcard_domain, cert_attributes, cert_attributes_other):
    """Certificate hierarchy used for the mTLS tests"""
    chain = {
        "envoy_ca": CertInfo(
            children={
                "envoy_cert": None,
                "valid_cert": CertInfo(names=[cert_attributes]),
                "custom_cert": CertInfo(names=[cert_attributes_other]),
                "intermediate_ca": CertInfo(
                    children={
                        "intermediate_valid_cert": CertInfo(names=[cert_attributes]),
                        "intermediate_custom_cert": CertInfo(names=[cert_attributes_other]),
                    }
                ),
                "intermediate_ca_unlabeled": CertInfo(
                    children={"intermediate_cert_unlabeled": CertInfo(names=[cert_attributes])}
                ),
            }
        ),
        "authorino_ca": CertInfo(
            children={
                "authorino_cert": CertInfo(hosts=authorino_domain),
            }
        ),
        "invalid_ca": CertInfo(children={"invalid_cert": None}),
        "self_signed_cert": None,
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def self_signed_cert(certificates):
    """Self-signed certificate"""
    return certificates["self_signed_cert"]
