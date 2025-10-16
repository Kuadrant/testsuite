""" " Conftest for general multicluster Limitador tests.

This conftest is responsible for retrieving the existing KuadrantCR instances
in each cluster. It then provides the base `limitador1` and `limitador2` fixtures."""

import pytest
from openshift_client import selector

from testsuite.kuadrant import KuadrantCR


@pytest.fixture(scope="session")
def kuadrant1(testconfig, cluster):
    """Returns the existing Kuadrant instance from the first cluster."""
    project = testconfig["service_protection"]["system_project"]
    kuadrant_cluster = cluster.change_project(project)

    with kuadrant_cluster.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)
    return kuadrant


@pytest.fixture(scope="session")
def kuadrant2(testconfig, cluster2):
    """Returns the existing Kuadrant instance from the second cluster."""
    project = testconfig["service_protection"]["system_project"]
    kuadrant_cluster = cluster2.change_project(project)

    with kuadrant_cluster.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)
    return kuadrant


@pytest.fixture(scope="session")
def limitador1(kuadrant1):
    """Returns the default LimitadorCR from the first cluster."""
    return kuadrant1.limitador


@pytest.fixture(scope="session")
def limitador2(kuadrant2):
    """Returns the default LimitadorCR from the second cluster."""
    return kuadrant2.limitador
