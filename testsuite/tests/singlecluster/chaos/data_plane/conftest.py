"""Conftest for data plane chaos testing."""

import pytest


@pytest.fixture(scope="module")
def authorino_selector():
    """Selector for Authorino pods."""
    return {"app": "authorino"}


@pytest.fixture(scope="module")
def limitador_selector():
    """Selector for Limitador pods."""
    return {"app": "limitador"}


@pytest.fixture(scope="module")
def data_plane_namespace():
    """Namespace where data plane components run."""
    return "kuadrant-system"


@pytest.fixture(scope="module")
def authorino_chaos_factory(create_pod_chaos, authorino_selector):
    """Factory fixture for creating Authorino chaos experiments."""
    def _create_authorino_chaos(name, action, **kwargs):
        chaos = create_pod_chaos(f"authorino-{name}")
        
        if action == "container-kill":
            chaos.container_kill(
                labels=authorino_selector,
                containers=kwargs.get("containers", ["authorino"]),
                duration=kwargs.get("duration", "10s"),
            )
        elif action == "pod-kill":
            chaos.pod_kill(
                labels=authorino_selector,
                grace_period=kwargs.get("grace_period", 0),
            )
        elif action == "pod-failure":
            chaos.pod_failure(
                labels=authorino_selector,
                duration=kwargs.get("duration", "30s"),
            )
        else:
            raise ValueError(f"Unsupported action: {action}")
            
        return chaos
    return _create_authorino_chaos


@pytest.fixture(scope="module")
def limitador_chaos_factory(create_pod_chaos, limitador_selector):
    """Factory fixture for creating Limitador chaos experiments."""
    def _create_limitador_chaos(name, action, **kwargs):
        chaos = create_pod_chaos(f"limitador-{name}")
        
        if action == "container-kill":
            chaos.container_kill(
                labels=limitador_selector,
                containers=kwargs.get("containers", ["limitador"]),
                duration=kwargs.get("duration", "10s"),
            )
        elif action == "pod-kill":
            chaos.pod_kill(
                labels=limitador_selector,
                grace_period=kwargs.get("grace_period", 0),
            )
        elif action == "pod-failure":
            chaos.pod_failure(
                labels=limitador_selector,
                duration=kwargs.get("duration", "30s"),
            )
        else:
            raise ValueError(f"Unsupported action: {action}")
            
        return chaos
    return _create_limitador_chaos


@pytest.fixture(scope="module")
def authorino_network_chaos(create_network_chaos, authorino_selector):
    """Creates NetworkChaos targeting Authorino."""
    def _create_network_chaos(name, action="delay", **kwargs):
        chaos = create_network_chaos(f"authorino-network-{name}")
        chaos.configure_network_chaos(
            labels=authorino_selector,
            action=action,
            **kwargs
        )
        return chaos
    return _create_network_chaos


@pytest.fixture(scope="module")
def limitador_network_chaos(create_network_chaos, limitador_selector):
    """Creates NetworkChaos targeting Limitador."""
    def _create_network_chaos(name, action="delay", **kwargs):
        chaos = create_network_chaos(f"limitador-network-{name}")
        chaos.configure_network_chaos(
            labels=limitador_selector,
            action=action,
            **kwargs
        )
        return chaos
    return _create_network_chaos
