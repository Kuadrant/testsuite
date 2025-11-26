"""Test DNSPolicy strategy conflict - two DNSPolicies use same hostname but different load-balancing strategies"""

import pytest
import dns.resolver

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import DNSPolicy, LoadBalancing, has_record_condition

pytestmark = [pytest.mark.multicluster]


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_server, module_label, dns_provider_secret):
    """DNSPolicy with different load-balancing strategy for the second cluster"""
    lb = LoadBalancing(defaultGeo=False, geo=dns_server["geo_code"])
    return DNSPolicy.create_instance(
        cluster2, blame("dns"), gateway2, dns_provider_secret, load_balancing=lb, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(
    request, routes, gateway, gateway2, dns_policy, dns_policy2, tls_policy, tls_policy2
):  # pylint: disable=unused-argument
    """Commits gateways and all policies before tests. Commits dns_policy2 last where conflict is expected to occur"""
    for component in [gateway, gateway2, dns_policy, tls_policy, tls_policy2]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()

    request.addfinalizer(dns_policy2.delete)
    dns_policy2.commit()


def test_lb_strategy_conflict(wildcard_domain, hostname, dns_policy2, gateway):
    """
    Test DNSPolicy load-balancing strategy conflict
    - Checks status messages on DNSPolicy and associated DNS record
    - Checks that DNS resolution returns only the first gateway IP address in A record set
    """
    assert dns_policy2.wait_until(has_condition("Enforced", "False"))
    assert dns_policy2.wait_until(
        has_record_condition(
            "Ready",
            "False",
            "ProviderError",
            "The DNS provider failed to ensure the record: record type conflict, cannot update "
            f"endpoint '{wildcard_domain}' with record type 'CNAME' when endpoint already exists with record type 'A'",
        )
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy2.model.status.recordConditions}"

    gw1_ip = gateway.external_ip().split(":")[0]
    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {gw1_ip} == dns_ips, "Only the first gateway IP address is expected in A record set"
