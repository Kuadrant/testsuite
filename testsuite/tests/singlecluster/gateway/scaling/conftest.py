import pytest
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


@pytest.fixture(scope="module")
def rate_limit(blame, gateway, module_label, cluster):
    """Add limit to the policy"""
    policy = RateLimitPolicy.create_instance(cluster, blame("rlp"), gateway, labels={"app": module_label})
    policy.add_limit("basic", [Limit(5, "5s")], when=[CelPredicate("auth.identity.userid != 'load-generator'")])
    return policy
