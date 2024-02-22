"""Tests that TLSPolicy is rejected if the issuer is invalid"""

import pytest
from openshift_client import selector

from testsuite.gateway import CustomReference
from testsuite.policy.tls_policy import TLSPolicy
from testsuite.utils import generate_tail

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def base_domain(hub_openshift):
    """Returns preconfigured base domain"""
    zone = selector("managedzone/aws-mz", static_context=hub_openshift.context).object()
    return f"{generate_tail()}.{zone.model['spec']['domainName']}"


def test_wrong_issuer_type(request, hub_gateway, hub_openshift, blame, module_label):
    """Tests that TLSPolicy is rejected if issuer does not have a correct type"""

    def wrong_issuer_type(policy):
        for condition in policy.model.status.conditions:
            if (
                condition.type == "Ready"
                and condition.status == "False"
                and 'invalid value "Gateway" for issuerRef.kind. Must be empty, "Issuer" or "ClusterIssuer"'
                in condition.message
                and condition.reason == "ReconciliationError"
            ):
                return True
        return False

    policy = TLSPolicy.create_instance(
        hub_openshift,
        blame("resource"),
        hub_gateway,
        hub_gateway,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(wrong_issuer_type), "Policy did not reach expected status"


def test_non_existing_issuer(request, hub_gateway, hub_openshift, blame, module_label):
    """Tests that TLSPolicy is rejected if issuer does not exist"""

    def wrong_issuer(policy):
        for condition in policy.model.status.conditions:
            if (
                condition.type == "Ready"
                and condition.status == "False"
                and 'ClusterIssuer.cert-manager.io "does-not-exist" not found' in condition.message
                and condition.reason == "ReconciliationError"
            ):
                return True
        return False

    policy = TLSPolicy.create_instance(
        hub_openshift,
        blame("resource"),
        hub_gateway,
        CustomReference(
            group="cert-manager.io",
            kind="ClusterIssuer",
            name="does-not-exist",
        ),
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(wrong_issuer), "Policy did not reach expected status"
