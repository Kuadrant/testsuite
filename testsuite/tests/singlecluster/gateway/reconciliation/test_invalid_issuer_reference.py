"""Tests that TLSPolicy is rejected if the issuer is invalid"""

import pytest

from testsuite.gateway import CustomReference
from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def commit():
    """We do not need any other resource"""
    return None


def test_wrong_issuer_type(request, gateway, blame, module_label, cluster):
    """Tests that TLSPolicy is rejected if issuer does not have a correct type"""

    policy = TLSPolicy.create_instance(
        gateway.cluster,
        blame("resource"),
        gateway,
        CustomReference(
            group="gateway.networking.k8s.io",
            kind="Gateway",
            name=gateway.name(),
        ),
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    res = cluster.do_action("create", "-f", "-", stdin_str=policy.as_json(), auto_raise=False)
    assert res.status() == 1, "Policy should not be created with invalid issuerRef.kind"
    assert res.err().strip() == (
        f'The TLSPolicy "{policy.model.metadata.name}" is invalid: spec.issuerRef: Invalid value: "object": '
        f"Invalid issuerRef.kind. The only supported values are blank, 'Issuer' and 'ClusterIssuer'"
    )


def test_non_existing_issuer(request, gateway, cluster, blame, module_label):
    """Tests that TLSPolicy is rejected if issuer does not exist"""

    policy = TLSPolicy.create_instance(
        cluster,
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
        has_condition("Accepted", "False", "Invalid", "TLSPolicy target is invalid: unable to find issuer"),
        timelimit=20,
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"
