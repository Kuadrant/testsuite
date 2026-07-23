"""Conftest for DNS failover tests using groups"""

import pytest

from testsuite.kuadrant.policy.dns import has_record_condition
from testsuite.utils import generate_tail

MAX_REQUEUE_TIME = 10


@pytest.fixture(scope="module")
def dns_operator_deployment(request, cluster, system_project):
    """DNS Operator deployment on the first cluster"""
    sys_ns = cluster.change_project(system_project.project)
    deployment = sys_ns.get_deployment("dns-operator-controller-manager")
    original_replicas = deployment.replicas
    request.addfinalizer(lambda: deployment.set_replicas(original_replicas))
    return deployment


@pytest.fixture(scope="module")
def group1():
    """Random group name for cluster 1"""
    return f"group1-{generate_tail(5)}"


@pytest.fixture(scope="module")
def group2():
    """Random group name for cluster 2"""
    return f"group2-{generate_tail(5)}"


@pytest.fixture(scope="module")
def configure_dns_failover_groups(request, cluster, cluster2, system_project, group1, group2):
    """Configure DNS Operator GROUP and MAX_REQUEUE_TIME on both clusters"""
    for cluster_client, group_id in [(cluster, group1), (cluster2, group2)]:
        sys_ns = cluster_client.change_project(system_project.project)

        dns_deployment = sys_ns.get_deployment("dns-operator-controller-manager")

        # add finalizer to remove the added variables and restart the controller, ORDER MATTERS
        request.addfinalizer(dns_deployment.restart)
        remove_patch = '{"data":{"GROUP":null,"MAX_REQUEUE_TIME":null}}'
        request.addfinalizer(
            lambda sys=sys_ns, p=remove_patch: sys.do_action(
                "patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", p
            )
        )

        # Patch the configmap to add/update GROUP and MAX_REQUEUE_TIME variables
        add_patch = f'{{"data":{{"GROUP":"{group_id}","MAX_REQUEUE_TIME":"{MAX_REQUEUE_TIME}s"}}}}'
        sys_ns.do_action("patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", add_patch)

        dns_deployment.restart()


@pytest.fixture(scope="module")
def add_active_groups(
    request, configure_dns_failover_groups, kubectl_dns, exposer, dns_provider_secret, cluster, group1, group2
):  # pylint: disable=unused-argument
    """Create active-groups TXT record with group1 as the initial active group"""
    provider_ref = f"{cluster.project}/{dns_provider_secret}"

    def _cleanup():
        for group in [group1, group2]:
            kubectl_dns.remove_active_group(cluster, group, domain=exposer.zone_domain, provider_ref=provider_ref)

    request.addfinalizer(_cleanup)
    result = kubectl_dns.add_active_group(cluster, group1, domain=exposer.zone_domain, provider_ref=provider_ref)
    assert result.returncode == 0, f"Failed to add active group: {result.stderr}"


@pytest.fixture(scope="module", autouse=True)
def commit(
    request,
    routes,
    gateway,
    gateway2,
    dns_policy,
    dns_policy2,
    tls_policy,
    tls_policy2,
    add_active_groups,
):  # pylint: disable=unused-argument
    """Commits gateways and all policies required for the test"""
    components = [gateway, gateway2, dns_policy, dns_policy2, tls_policy, tls_policy2]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()

    for component in [gateway, gateway2, tls_policy, tls_policy2]:
        component.wait_for_ready()

    dns_policy.wait_for_ready()

    dns_policy2.wait_for_accepted()
    assert dns_policy2.wait_until(
        has_record_condition("Active", "False", "NotMemberOfActiveGroup", "Group is not included in active groups")
    ), f"dns_policy2 should report inactive group, got: {dns_policy2.model.status.recordConditions}"
    assert dns_policy2.wait_until(
        has_record_condition(
            "Ready", "False", "MemberOfInactiveGroup", "No further actions to take while in inactive group"
        )
    ), f"dns_policy2 should report inactive group not ready, got: {dns_policy2.model.status.recordConditions}"
