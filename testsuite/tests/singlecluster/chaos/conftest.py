"""Conftest for chaos testing."""

import pytest
import openshift_client as oc

from testsuite.chaos_mesh import PodChaos


@pytest.fixture(scope="module")
def create_pod_chaos(request, cluster, blame):
    """Creates and returns a PodChaos experiment."""

    def _create_pod_chaos(name, namespace="kuadrant-system"):
        chaos = PodChaos.create_instance(cluster, blame(name), namespace=namespace)
        request.addfinalizer(chaos.delete)
        return chaos

    return _create_pod_chaos


@pytest.fixture(scope="module")
def kuadrant_operator_pod_chaos(create_pod_chaos):
    """Creates a PodChaos experiment targeting the Kuadrant operator."""
    chaos = create_pod_chaos("operator-kill")
    chaos.container_kill(
        labels={"app": "kuadrant"},
        containers=["manager"],
    )
    return chaos


@pytest.fixture(autouse=True)
def restart_operator(cluster):
    """Restart the Kuadrant operator deployment after each test."""
    yield  # Run the test first

    # After test, delete the pod to force a restart
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        # Find and delete the operator pod
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        pod.delete()


@pytest.fixture(autouse=True)
def commit():
    """Override commit fixture to do nothing."""
    pass
