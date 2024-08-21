"""Tests that DNSPolicy/TLSPolicy is rejected if the Gateway does not exist at all"""

import pytest

from testsuite.gateway import CustomReference
from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def commit():
    """We do not need any other resource"""
    return None


@pytest.mark.parametrize(
    "policy_cr, issuer_or_secret",
    [
        pytest.param(DNSPolicy, "dns_provider_secret", id="DNSPolicy", marks=[pytest.mark.dnspolicy]),
        pytest.param(TLSPolicy, "cluster_issuer", id="TLSPolicy", marks=[pytest.mark.tlspolicy]),
    ],
)
@pytest.mark.issue("https://github.com/Kuadrant/multicluster-gateway-controller/issues/361")
def test_no_gw(request, policy_cr, issuer_or_secret, cluster, blame, module_label):
    """Tests that policy is rejected if the Gateway does not exist at all"""
    # depending on if DNSPolicy or TLSPolicy is tested the right object for the 4th parameter is passed
    issuer_or_secret_obj = request.getfixturevalue(issuer_or_secret)
    policy = policy_cr.create_instance(
        cluster,
        blame("resource"),
        CustomReference(group="gateway.networking.k8s.io", kind="Gateway", name="does-not-exist"),
        issuer_or_secret_obj,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "TargetNotFound", "target does-not-exist was not found"), timelimit=20
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"
