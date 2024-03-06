"""Tests that DNSPolicy/TLSPolicy is rejected if the Gateway does not exist at all"""

import pytest

from testsuite.gateway import CustomReference
from testsuite.policy.tls_policy import TLSPolicy
from testsuite.tests.mgc.reconciliation import dns_policy

pytestmark = [pytest.mark.mgc]


@pytest.mark.parametrize(
    "create_cr", [pytest.param(dns_policy, id="DNSPolicy"), pytest.param(TLSPolicy.create_instance, id="TLSPolicy")]
)
@pytest.mark.issue("https://github.com/Kuadrant/multicluster-gateway-controller/issues/361")
def test_no_gw(request, create_cr, hub_openshift, blame, module_label, cluster_issuer):
    """Tests that policy is rejected if the Gateway does not exist at all"""

    def target_not_found(policy):
        for condition in policy.model.status.conditions:
            if (
                condition.type == "Ready"
                and condition.status == "False"
                and 'Gateway.gateway.networking.k8s.io "does-not-exist" not found' in condition.message
                and condition.reason == "TargetNotFound"
            ):
                return True
        return False

    policy = create_cr(
        hub_openshift,
        blame("resource"),
        CustomReference(group="gateway.networking.k8s.io", kind="Gateway", name="does-not-exist"),
        cluster_issuer,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(target_not_found), "Policy did not reach expected status"
