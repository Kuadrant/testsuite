"""Conftest for control plane chaos testing."""

import pytest

@pytest.fixture(scope="module")
def kuadrant_operator_selector():
    """Selector for Kuadrant operator pods."""
    return {"app": "kuadrant"}


@pytest.fixture(scope="module")
def control_plane_namespace():
    """Namespace where control plane components run."""
    return "kuadrant-system"


@pytest.fixture(scope="module")
def operator_chaos_factory(create_pod_chaos, kuadrant_operator_selector):
    """Factory fixture for creating operator chaos experiments."""
    def _create_operator_chaos(name, action, **kwargs):
        chaos = create_pod_chaos(f"operator-{name}")
        
        if action == "container-kill":
            chaos.container_kill(
                labels=kuadrant_operator_selector,
                containers=kwargs.get("containers", ["manager"]),
            )
        elif action == "pod-kill":
            chaos.pod_kill(
                labels=kuadrant_operator_selector,
                grace_period=kwargs.get("grace_period", 0),
            )
        elif action == "pod-failure":
            chaos.pod_failure(
                labels=kuadrant_operator_selector,
            )
        else:
            raise ValueError(f"Unsupported action: {action}")
            
        return chaos
    return _create_operator_chaos


@pytest.fixture(scope="module")
def operator_network_chaos(create_network_chaos, kuadrant_operator_selector):
    """Creates NetworkChaos targeting the Kuadrant operator."""
    def _create_network_chaos(name, action="delay", **kwargs):
        chaos = create_network_chaos(f"operator-network-{name}")
        chaos.configure_network_chaos(
            labels=kuadrant_operator_selector,
            action=action,
            **kwargs
        )
        return chaos
    return _create_network_chaos


@pytest.fixture(scope="module")
def operator_stress_chaos(create_stress_chaos, kuadrant_operator_selector):
    """Creates StressChaos targeting the Kuadrant operator."""
    def _create_stress_chaos(name, stress_type="memory", **kwargs):
        chaos = create_stress_chaos(f"operator-stress-{name}")
        chaos.configure_stress(
            labels=kuadrant_operator_selector,
            stress_type=stress_type,
            **kwargs
        )
        return chaos
    return _create_stress_chaos
