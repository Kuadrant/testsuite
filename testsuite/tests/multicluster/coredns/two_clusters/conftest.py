"""Shared fixtures for all two-cluster coredns tests"""

import pytest


@pytest.fixture(scope="module", autouse=True)
def commit(request, coredns_secrets, kubeconfig_secrets, dnsrecord1, dnsrecord2):  # pylint: disable=unused-argument
    """Commits all components required for the test and adds finalizers to delete them on cleanup"""
    for component in [*kubeconfig_secrets, dnsrecord1, dnsrecord2]:
        request.addfinalizer(component.delete)
        component.commit()
    for component in [dnsrecord1, dnsrecord2]:
        component.wait_for_ready()
