"""Tests that TLSPolicy is rejected if the issuer is invalid"""

import pytest

from testsuite.gateway import CustomReference
from testsuite.policy.tls_policy import TLSPolicy
from testsuite.utils import has_condition

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def commit():
    """We do not need any other resource"""
    return None


def test_wrong_issuer_type(request, gateway, blame, module_label):
    """Tests that TLSPolicy is rejected if issuer does not have a correct type"""

    policy = TLSPolicy.create_instance(
        gateway.openshift,
        blame("resource"),
        gateway,
        gateway,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition(
            "Accepted",
            "False",
            "Unknown",
            'invalid value "Gateway" for issuerRef.kind. Must be empty, "Issuer" or "ClusterIssuer"',
        ),
        timelimit=20,
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"


def test_non_existing_issuer(request, gateway, hub_openshift, blame, module_label):
    """Tests that TLSPolicy is rejected if issuer does not exist"""

    policy = TLSPolicy.create_instance(
        hub_openshift,
        blame("resource"),
        gateway,
        CustomReference(
            group="cert-manager.io",
            kind="ClusterIssuer",
            name="does-not-exist",
        ),
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown", 'ClusterIssuer.cert-manager.io "does-not-exist" not found'),
        timelimit=20,
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"
