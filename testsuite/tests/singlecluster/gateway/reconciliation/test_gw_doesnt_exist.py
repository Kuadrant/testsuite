"""Tests that DNSPolicy/TLSPolicy is rejected if the Gateway does not exist at all"""

import pytest

from testsuite.gateway import CustomReference
from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.kuadrant.policy import has_condition
from . import dns_policy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def commit():
    """We do not need any other resource"""
    return None


@pytest.mark.parametrize(
    "create_cr",
    [
        pytest.param(dns_policy, id="DNSPolicy", marks=[pytest.mark.dnspolicy]),
        pytest.param(TLSPolicy.create_instance, id="TLSPolicy", marks=[pytest.mark.tlspolicy]),
    ],
)
@pytest.mark.issue("https://github.com/Kuadrant/multicluster-gateway-controller/issues/361")
def test_no_gw(request, create_cr, cluster, blame, module_label, cluster_issuer):
    """Tests that policy is rejected if the Gateway does not exist at all"""

    policy = create_cr(
        cluster,
        blame("resource"),
        CustomReference(group="gateway.networking.k8s.io", kind="Gateway", name="does-not-exist"),
        cluster_issuer,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "TargetNotFound", "target does-not-exist was not found"), timelimit=20
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"
