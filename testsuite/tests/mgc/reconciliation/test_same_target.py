"""Tests that DNSPolicy/TLSPolicy is rejected when the Gateway already has a policy of the same kind"""

import pytest
from openshift_client import selector

from testsuite.policy.tls_policy import TLSPolicy
from testsuite.tests.mgc.reconciliation import dns_policy
from testsuite.utils import generate_tail

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def base_domain(hub_openshift):
    """Returns preconfigured base domain"""
    zone = selector("managedzone/aws-mz", static_context=hub_openshift.context).object()
    return f"{generate_tail()}.{zone.model['spec']['domainName']}"


@pytest.mark.parametrize(
    "create_cr", [pytest.param(dns_policy, id="DNSPolicy"), pytest.param(TLSPolicy.create_instance, id="TLSPolicy")]
)
def test_two_policies_one_gw(request, create_cr, hub_gateway, client, blame, module_label, cluster_issuer):
    """Tests that policy is rejected when the Gateway already has a DNSPolicy"""

    def two_dns_policies_error(policy):
        for condition in policy.model.status.conditions:
            if (
                condition.type == "Ready"
                and condition.status == "False"
                and condition.reason == "ReconciliationError"
                and "is already referenced by policy" in condition.message
            ):
                return True
        return False

    # test that it works before the policy
    response = client.get("get")
    assert response.status_code == 200, "Original DNSPolicy does not work"

    policy = create_cr(
        hub_gateway.openshift,
        blame("dns2"),
        hub_gateway,
        cluster_issuer,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    # Wait for expected status
    assert policy.wait_until(two_dns_policies_error), "Policy did not reach expected status"

    # Test that the original policy still works
    response = client.get("get")
    assert response.status_code == 200
