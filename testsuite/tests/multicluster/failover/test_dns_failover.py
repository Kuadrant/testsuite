"""Test DNS failover from one cluster to another using DNS Operator active groups"""

import time

import dns.resolver
import pytest

from testsuite.tests.multicluster.failover.conftest import MAX_REQUEUE_TIME
from testsuite.utils import sleep_ttl

pytestmark = [pytest.mark.multicluster, pytest.mark.disruptive, pytest.mark.flaky(reruns=0)]


def test_dns_failover(
    cluster,
    exposer,
    client,
    hostname,
    dns_provider_secret,
    gateway,
    gateway2,
    dns_policy2,
    dns_operator_deployment,
    kubectl_dns,
    group1,
    group2,
):  # pylint: disable=too-many-locals
    """
    Test DNS failover from group1 (cluster1) to group2 (cluster2):
    1. Verify initial state with DNS resolving to cluster1
    2. Scale down DNS operator on cluster1 to simulate failure
    3. Switch active group from group1 to group2
    4. Verify DNS resolves to cluster2 after failover
    """
    gw1_ip = gateway.external_ip().split(":")[0]
    gw2_ip = gateway2.external_ip().split(":")[0]

    response = client.get("/get")
    assert not response.has_dns_error(), response.error
    assert response.status_code == 200

    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {gw1_ip} == dns_ips, f"Initially DNS should only resolve to cluster1 IP ({gw1_ip}), got {dns_ips}"

    # scale down DNS operator on cluster1 to simulate failure
    dns_operator_deployment.set_replicas(0)

    # make second cluster group active and first cluster group inactive
    provider_ref = f"{cluster.project}/{dns_provider_secret}"
    result = kubectl_dns.add_active_group(cluster, group2, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to add group2 to active groups: {result.stderr}"
    result = kubectl_dns.remove_active_group(cluster, group1, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to remove group1 from active groups: {result.stderr}"

    time.sleep(MAX_REQUEUE_TIME)  # wait for DNS operator to process the change
    dns_policy2.wait_for_ready()
    sleep_ttl(hostname.hostname)

    response = client.get("/get")
    assert not response.has_dns_error(), response.error
    assert response.status_code == 200

    dns_ips = {ip.address for ip in dns.resolver.resolve(hostname.hostname)}
    assert {gw2_ip} == dns_ips, f"After failover DNS should only resolve to cluster2 IP ({gw2_ip}), got {dns_ips}"
