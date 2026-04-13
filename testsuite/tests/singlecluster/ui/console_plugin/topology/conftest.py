"""Conftest for topology UI tests"""

import pytest
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.tls import TLSPolicy


@pytest.fixture(scope="module")
def authorization(authorization):
    """Configure AuthPolicy for topology tests"""
    authorization.authorization.add_opa_policy("denyAll", "allow = false")
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Configure RateLimitPolicy for topology tests"""
    rate_limit.add_limit("basic", [Limit(5, "10s")])
    return rate_limit


@pytest.fixture(scope="module")
def dns_policy(gateway, cluster, blame, module_label):
    """Create DNSPolicy for topology tests"""
    return DNSPolicy.create_instance(cluster, blame("dns"), gateway, labels={"app": module_label})


@pytest.fixture(scope="module")
def tls_policy(gateway, cluster, blame, cluster_issuer, module_label):
    """Create TLSPolicy for topology tests"""
    return TLSPolicy.create_instance(
        cluster, blame("tls"), gateway, issuer=cluster_issuer, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commit all policies before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_accepted()
