"""Conftest for load-balanced multicluster tests"""

import pytest
from dynaconf import ValidationError

from testsuite.kuadrant.policy.dns import DNSPolicy, LoadBalancing


@pytest.fixture(scope="package")
def dns_config(testconfig, skip_or_fail):
    """Configuration for DNS tests"""
    try:
        testconfig.validators.validate(only=["dns.dns_server", "dns.dns_server2"])
        return testconfig["dns"]
    except ValidationError as exc:
        return skip_or_fail(f"DNS servers configuration is missing: {exc}")


@pytest.fixture(scope="package")
def dns_server(dns_config):
    """DNS server in the first geo region"""
    return dns_config["dns_server"]


@pytest.fixture(scope="package")
def dns_server2(dns_config):
    """DNS server in the second geo region"""
    return dns_config["dns_server2"]


@pytest.fixture(scope="session")
def dns_default_geo_server(testconfig, skip_or_fail):
    """Configuration of DNS server for default GEO tests"""
    try:
        testconfig.validators.validate(only="dns.default_geo_server")
        return testconfig["dns"]["default_geo_server"]
    except ValidationError as exc:
        return skip_or_fail(f"DNS default geo server configuration is missing: {exc}")


@pytest.fixture(scope="module")
def dns_policy(blame, cluster, gateway, dns_server, module_label, dns_provider_secret):
    """DNSPolicy with load-balancing for the first cluster"""
    load_balancing = LoadBalancing(defaultGeo=True, geo=dns_server["geo_code"])
    return DNSPolicy.create_instance(
        cluster, blame("dns"), gateway, dns_provider_secret, load_balancing=load_balancing, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_server2, module_label, dns_provider_secret):
    """DNSPolicy with load-balancing for the second cluster"""
    load_balancing = LoadBalancing(defaultGeo=False, geo=dns_server2["geo_code"])
    return DNSPolicy.create_instance(
        cluster2,
        blame("dns"),
        gateway2,
        dns_provider_secret,
        load_balancing=load_balancing,
        labels={"app": module_label},
    )
