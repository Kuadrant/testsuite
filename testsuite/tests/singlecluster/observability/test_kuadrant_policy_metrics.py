"""Tests for Kuadrant policy metrics (policies total and policies enforced per policy kind)."""

import pytest

from testsuite.gateway import Exposer, TLSGatewayListener
from testsuite.prometheus import has_label
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy

pytestmark = [pytest.mark.observability]

POLICY_KINDS = ["AuthPolicy", "RateLimitPolicy", "DNSPolicy", "TLSPolicy", "TokenRateLimitPolicy"]


@pytest.fixture(scope="module")
def exposer(request, cluster) -> Exposer:
    """DNSPolicyExposer setup with expected TLS certificate"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def base_domain(exposer):
    """Returns preconfigured base domain from DNS provider"""
    return exposer.base_domain


@pytest.fixture(scope="module")
def wildcard_domain(base_domain):
    """Wildcard domain for the exposer"""
    return f"*.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Returns gateway with TLS listener for DNS/TLS policy support"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def authorization(cluster, blame, route, module_label):
    """Create AuthPolicy targeting the route with anonymous identity"""
    policy = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"testRun": module_label})
    policy.identity.add_anonymous("anonymous")
    return policy


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, route, module_label):
    """Create RateLimitPolicy targeting the route"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    return policy


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Create TokenRateLimitPolicy targeting the route"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    return policy


@pytest.fixture(scope="module")
def dns_policy(cluster, blame, gateway, module_label, dns_provider_secret):
    """Create DNSPolicy targeting the gateway"""
    return DNSPolicy.create_instance(
        cluster, blame("dns"), gateway, dns_provider_secret, labels={"testRun": module_label}
    )


@pytest.fixture(scope="module")
def tls_policy(cluster, blame, gateway, module_label, cluster_issuer):
    """Create TLSPolicy targeting the gateway"""
    return TLSPolicy.create_instance(
        cluster, blame("tls"), parent=gateway, issuer=cluster_issuer, labels={"testRun": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, token_rate_limit, dns_policy, tls_policy):
    """Commit all policies and register finalizers for cleanup"""
    for component in [dns_policy, tls_policy, authorization, rate_limit, token_rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


@pytest.mark.parametrize("kind", POLICY_KINDS)
def test_metric_kuadrant_policies_total(operator_metrics, kind):
    """Tests that kuadrant_policies_total metric has value >= 1 for each policy kind"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_policies_total")).filter(has_label("kind", kind))
    assert metrics.values, f"No values returned for 'kuadrant_policies_total' for kind '{kind}'"
    assert (
        metrics.values[0] >= 1
    ), f"Expected 'kuadrant_policies_total' for kind '{kind}' to have value >= 1, but got: {metrics.values}"


@pytest.mark.parametrize("kind", POLICY_KINDS)
def test_metric_kuadrant_policies_enforced(operator_metrics, kind):
    """Tests that kuadrant_policies_enforced metric has value >= 1 for each enforced policy kind"""
    metrics = (
        operator_metrics.filter(has_label("__name__", "kuadrant_policies_enforced"))
        .filter(has_label("kind", kind))
        .filter(has_label("status", "true"))
    )
    assert metrics.values, f"No values returned for 'kuadrant_policies_enforced' for kind '{kind}'"
    assert (
        metrics.values[0] >= 1
    ), f"Expected 'kuadrant_policies_enforced' for kind '{kind}' to have value >= 1, but got: {metrics.values}"
