"""Test changing load-balancing strategy in DNSPolicy"""

import pytest

pytestmark = [pytest.mark.multicluster]


def test_change_lb_strategy(dns_policy2):
    """Verify that changing load-balancing strategy is not allowed"""
    dns_policy2.model.spec.pop("loadBalancing")
    res = dns_policy2.apply()

    assert res.status() == 1
    assert "loadBalancing is immutable" in res.err()
