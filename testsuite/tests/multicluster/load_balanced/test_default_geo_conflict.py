"""Test that dns-operator correctly handles situation when more than one DNSPolicy has defaultGeo set to True"""

from time import sleep
import pytest

from testsuite.kuadrant.policy.dns import DNSPolicy, LoadBalancing, has_record_condition

pytestmark = [pytest.mark.multicluster]


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_server2, module_label, dns_provider_secret):
    """Second cluster DNSPolicy with defaultGeo also set to True"""
    lb = LoadBalancing(defaultGeo=True, geo=dns_server2["geo_code"])
    return DNSPolicy.create_instance(
        cluster2, blame("dns"), gateway2, dns_provider_secret, load_balancing=lb, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(
    request, routes, gateway, gateway2, dns_policy, dns_policy2, tls_policy, tls_policy2
):  # pylint: disable=unused-argument
    """Commits gateways and all policies for the test. Default geo conflict is expected to occur with dns policies"""
    for component in [gateway, gateway2, dns_policy, dns_policy2, tls_policy, tls_policy2]:
        request.addfinalizer(component.delete)
        component.commit()

    for component in [gateway, gateway2, tls_policy, tls_policy2]:
        component.wait_for_ready()
    for component in [dns_policy, dns_policy2]:
        component.wait_for_accepted()


def test_default_geo_conflict(dns_policy, dns_policy2):
    """Verify that when two DNSPolicies have defaultGeo=True, both policies enter the await validation state"""
    sleep(60)  # wait a bit for records between two clusters to synchronize

    assert dns_policy.wait_until(
        has_record_condition("Ready", "False", "AwaitingValidation", "Awaiting validation"), timelimit=450
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy2.model.status.recordConditions}"
    assert dns_policy2.wait_until(
        has_record_condition("Ready", "False", "AwaitingValidation", "Awaiting validation"), timelimit=450
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy2.model.status.recordConditions}"
