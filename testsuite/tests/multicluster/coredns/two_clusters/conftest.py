"""Shared fixtures for all two-cluster coredns tests"""

import pytest


@pytest.fixture(scope="module")
def set_delegate_mode(request, cluster2, testconfig):
    """Configures secondary cluster by patching dns-operator-controller-env configmap with DELEGATION_ROLE: secondary"""
    system_project = cluster2.change_project(testconfig["service_protection"]["system_project"])

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


@pytest.fixture(scope="module", autouse=True)
def commit(request, coredns_secrets, kubeconfig_secrets, dnsrecord1, dnsrecord2):  # pylint: disable=unused-argument
    """Commits all components required for the test and adds finalizers to delete them on cleanup"""
    for component in [*kubeconfig_secrets, dnsrecord1, dnsrecord2]:
        request.addfinalizer(component.delete)
        component.commit()
    for component in [dnsrecord1, dnsrecord2]:
        component.wait_for_ready()
