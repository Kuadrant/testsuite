"""Test that server raises error when both delegate is true and providerRefs are set"""

import pytest

from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.dns import DNSPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label, dns_provider_secret):
    """Return DNSPolicy with delegate true and providerRefs secret"""
    return DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, delegate=True, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit():
    """Commiting is done inside the test"""


def test_delegate_true_and_provider_ref_are_mutually_exclusive(dns_policy):
    """Test that server raises error when both delegate is true and providerRefs are set"""
    with pytest.raises(OpenShiftPythonException, match="delegate=true and providerRefs are mutually exclusive"):
        dns_policy.commit()
