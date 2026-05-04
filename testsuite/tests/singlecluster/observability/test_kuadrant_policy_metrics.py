"""Tests for Kuadrant policy metrics (policies total and policies enforced per policy kind)."""

import operator

import pytest

from testsuite.gateway import Exposer, TLSGatewayListener
from testsuite.prometheus import has_label
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy

pytestmark = [pytest.mark.observability]

POLICY_KINDS = ["AuthPolicy", "RateLimitPolicy", "DNSPolicy", "TLSPolicy", "TokenRateLimitPolicy"]


@pytest.fixture(scope="module")
def dns_exposer(request, cluster) -> Exposer:
    """DNSPolicyExposer for DNS/TLS tests"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def dns_base_domain(dns_exposer):
    """DNS base domain for DNS/TLS tests"""
    return dns_exposer.base_domain


@pytest.fixture(scope="module")
def dns_wildcard_domain(dns_base_domain):
    """DNS wildcard domain for DNS/TLS tests"""
    return f"*.{dns_base_domain}"


@pytest.fixture(scope="module")
def hostname(gateway, dns_exposer, domain_name):
    """Override to use dns_exposer instead of session exposer"""
    return dns_exposer.expose_hostname(domain_name, gateway)


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, dns_wildcard_domain, module_label):
    """Returns gateway with TLS listener for DNS/TLS policy support"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=dns_wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def authorization(authorization):
    """Create AuthPolicy targeting the route with anonymous identity"""
    authorization.identity.add_anonymous("anonymous")
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Create RateLimitPolicy targeting the route"""
    rate_limit.add_limit("basic", [Limit(5, "10s")])
    return rate_limit


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


@pytest.mark.parametrize("policy_kind", POLICY_KINDS)
def test_metric_kuadrant_policies_total(kuadrant_operator_metrics, policy_kind):
    """Tests that kuadrant_policies_total metric has value >= 1 for each policy kind"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_policies_total")).filter(
        has_label("kind", policy_kind)
    )
    assert metrics, f"'kuadrant_policies_total' metric wasn't found for kind '{policy_kind}'"
    assert (
        metrics.values[0] >= 1
    ), f"Expected 'kuadrant_policies_total' for kind '{policy_kind}' to have value >= 1, but got: {metrics.values}"


@pytest.mark.parametrize("policy_kind", POLICY_KINDS)
def test_metric_kuadrant_policies_enforced(prometheus, policy_kind, system_project):
    """Tests that kuadrant_policies_enforced metric has value >= 1 for each enforced policy kind"""
    labels = {
        "service": "kuadrant-operator-metrics",
        "namespace": system_project.project,
        "kind": policy_kind,
        "status": "true",
    }
    assert prometheus.wait_for_metric("kuadrant_policies_enforced", 1, labels=labels, compare=operator.ge), (
        f"Expected 'kuadrant_policies_enforced' for kind '{policy_kind}' "
        f"to have value >= 1, but got: {prometheus.get_metrics(key='kuadrant_policies_enforced', labels=labels).values}"
    )
