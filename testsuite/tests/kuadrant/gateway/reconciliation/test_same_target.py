"""Tests that DNSPolicy/TLSPolicy is rejected when the Gateway already has a policy of the same kind"""

import pytest

from testsuite.policy.tls_policy import TLSPolicy
from testsuite.policy import has_condition
from . import dns_policy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.mark.parametrize(
    "create_cr",
    [
        pytest.param(dns_policy, id="DNSPolicy", marks=[pytest.mark.dnspolicy]),
        pytest.param(TLSPolicy.create_instance, id="TLSPolicy", marks=[pytest.mark.tlspolicy]),
    ],
)
def test_two_policies_one_gw(request, create_cr, gateway, client, blame, module_label, cluster_issuer, auth):
    """Tests that policy is rejected when the Gateway already has a DNSPolicy"""

    # test that it works before the policy
    response = client.get("get", auth=auth)
    assert response.status_code == 200, "Original DNSPolicy does not work"

    policy = create_cr(
        gateway.cluster,
        blame("dns2"),
        gateway,
        cluster_issuer,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()

    # Wait for expected status
    assert policy.wait_until(
        has_condition("Accepted", "False", "Conflicted", "is already referenced by policy"), timelimit=20
    ), f"Policy did not reach expected status, instead it was: {policy.refresh().model.status.conditions}"

    # Test that the original policy still works
    response = client.get("get", auth=auth)
    assert response.status_code == 200
