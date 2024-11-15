"""Tests that DNSPolicy/TLSPolicy is rejected when the Gateway already has a policy of the same kind"""

import pytest

from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only]


@pytest.mark.parametrize(
    "policy_cr, policy_affected, issuer_or_secret",
    [
        pytest.param(DNSPolicy, "dns_policy", "dns_provider_secret", id="DNSPolicy", marks=[pytest.mark.dnspolicy]),
        pytest.param(TLSPolicy, "tls_policy", "cluster_issuer", id="TLSPolicy", marks=[pytest.mark.tlspolicy]),
    ],
)
def test_two_policies_one_gw(
    request, policy_cr, policy_affected, issuer_or_secret, gateway, client, blame, module_label, auth
):
    """Tests that policy is rejected when the Gateway already has a DNSPolicy"""

    # test that it works before the policy
    response = client.get("get", auth=auth)
    assert response.status_code == 200, "Original DNSPolicy does not work"

    # depending on if DNSPolicy or TLSPolicy is tested the right object for the 4th parameter is passed
    issuer_or_secret_obj = request.getfixturevalue(issuer_or_secret)
    policy_new = policy_cr.create_instance(
        gateway.cluster,
        blame("dns2"),
        gateway,
        issuer_or_secret_obj,
        labels={"app": module_label},
    )
    request.addfinalizer(policy_new.delete)
    policy_new.commit()

    policy = request.getfixturevalue(policy_affected)
    assert policy_new.wait_until(
        has_condition(
            "Accepted",
            "False",
            "Conflicted",
            f"{policy_new.model.kind} is conflicted by {policy.namespace()}/{policy.name()}: conflicting policy",
        ),
        timelimit=20,
    ), f"Policy did not reach expected status, instead it was: {policy_new.refresh().model.status.conditions}"

    # Test that the original policy still works
    response = client.get("get", auth=auth)
    assert response.status_code == 200
