"""Shared fixtures for all three-cluster coredns tests"""

import pytest

from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy.dns import DNSRecord, DNSRecordEndpoint

IP3 = "1.2.3.4"


@pytest.fixture(scope="package")
def cluster3(testconfig):
    """Kubernetes client for the third cluster"""
    if not testconfig["control_plane"]["cluster3"]:
        pytest.skip("Third cluster is not configured properly")

    project = testconfig["service_protection"]["project"]
    client = testconfig["control_plane"]["cluster3"].change_project(project)
    if not client.connected:
        pytest.fail(f"You are not logged into the THIRD cluster or the {project} namespace doesn't exist")
    return client


@pytest.fixture(scope="module")
def set_delegate_mode(request, cluster3, testconfig):
    """Configures cluster3 as a secondary cluster by patching dns-operator configmap with DELEGATION_ROLE: secondary"""
    system_project = cluster3.change_project(testconfig["service_protection"]["system_project"])

    # add finalizer to remove the DELEGATION_ROLE patch and restart the controller, ORDER MATTERS
    dns_operator_controller = system_project.get_deployment("dns-operator-controller-manager")
    request.addfinalizer(dns_operator_controller.restart)
    remove_patch = '{"data":{"DELEGATION_ROLE":null}}'
    request.addfinalizer(
        lambda: system_project.do_action(
            "patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", remove_patch
        )
    )

    # Patch the configmap to add/update DELEGATION_ROLE: secondary
    add_patch = '{"data":{"DELEGATION_ROLE":"secondary"}}'
    system_project.do_action("patch", "configmap", "dns-operator-controller-env", "--type=merge", "-p", add_patch)

    dns_operator_controller.restart()


@pytest.fixture(scope="module")
def coredns_secrets(
    request, set_delegate_mode, coredns_secrets, cluster, cluster2, cluster3, testconfig, blame, module_label
):  # pylint: disable=unused-argument
    """CoreDNS secrets for both clusters"""
    secret = Secret.create_instance(
        cluster3,
        blame("coredns"),
        {"ZONES": testconfig["dns"]["coredns_zone"]},
        secret_type="kuadrant.io/coredns",
        labels={"kuadrant.io/default-provider": "true", "app": module_label},
    )
    request.addfinalizer(secret.delete)
    secret.commit()


@pytest.fixture(scope="module")
def dnsrecord3(cluster3, testconfig, hostname, blame, module_label):
    """Return a DNSRecord instance ready for commit"""
    return DNSRecord.create_instance(
        cluster3,
        blame("rcrd3"),
        testconfig["dns"]["coredns_zone"],
        endpoints=[DNSRecordEndpoint(dnsName=hostname.hostname, recordType="A", recordTTL=60, targets=[IP3])],
        delegate=True,
        labels={"app": module_label},
    )


@pytest.fixture(scope="module", autouse=True)
def commit(
    request, coredns_secrets, kubeconfig_secrets, dnsrecord1, dnsrecord2, dnsrecord3
):  # pylint: disable=unused-argument
    """Commits all components required for the test and adds finalizers to delete them on cleanup"""
    for component in [*kubeconfig_secrets, dnsrecord1, dnsrecord2, dnsrecord3]:
        request.addfinalizer(component.delete)
        component.commit()
    for component in [dnsrecord1, dnsrecord2, dnsrecord3]:
        component.wait_for_ready()
