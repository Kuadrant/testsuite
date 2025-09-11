"""Conftest for chaos testing."""

import pytest

from testsuite.chaos_mesh import PodChaos


@pytest.fixture(scope="module")
def create_pod_chaos(request, cluster, blame):
    """Creates and returns a PodChaos experiment.
    
    Args:
        request: pytest request object
        cluster: Kubernetes cluster instance
        blame: Fixture to generate unique names
        
    Returns:
        Callable: Function to create PodChaos instances
    """
    def _create_pod_chaos(name, namespace="kuadrant-system"):
        chaos = PodChaos.create_instance(cluster, blame(name), namespace=namespace)
        request.addfinalizer(chaos.delete)
        return chaos

    return _create_pod_chaos


@pytest.fixture(scope="module")
def operator_pod_chaos(create_pod_chaos):
    """Creates a PodChaos experiment targeting the Kuadrant operator.
    
    Args:
        create_pod_chaos: Factory fixture for PodChaos
        
    Returns:
        PodChaos: Configured PodChaos instance
    """
    chaos = create_pod_chaos("operator-kill")
    chaos.container_kill(
        labels={"app": "kuadrant"},
        containers=["manager"],
        duration="10s"
    )
    return chaos