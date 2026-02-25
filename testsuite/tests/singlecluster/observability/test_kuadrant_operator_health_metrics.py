"""Tests for Kuadrant operator health metrics (existence, readiness, component and dependency status)."""

import pytest

from testsuite.prometheus import has_label

pytestmark = [pytest.mark.observability]

COMPONENTS = ["authorino", "limitador"]
DEPENDENCIES = ["authorino-operator", "limitador-operator", "cert-manager", "dns-operator", "istio", "envoygateway"]
CONTROLLERS = [
    "auth_policies",
    "rate_limit_policies",
    "dns_policies",
    "tls_policies",
    "istio_integration",
    "envoygateway_integration",
]


def test_metric_kuadrant_exist(operator_metrics):
    """Tests that kuadrant_exists metric is present and has value 1"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_exists"))
    assert metrics.values, "No values returned for 'kuadrant_exists'"
    assert metrics.values[0] == 1, f"Expected 'kuadrant_exists' to have value 1, but got values: {metrics.values}"


def test_metric_kuadrant_ready(operator_metrics, kuadrant):
    """Tests that kuadrant_ready metric is present and has value 1"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_ready")).filter(
        has_label("name", kuadrant.name())
    )
    assert metrics.values, "No values returned for 'kuadrant_ready'"
    assert metrics.values[0] == 1, f"Expected 'kuadrant_ready' to have value 1, but got values: {metrics.values}"


@pytest.mark.parametrize("component", COMPONENTS)
def test_metric_kuadrant_component_ready(operator_metrics, component):
    """Tests that kuadrant_component_ready metric is present and has value 1 for each component"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_component_ready")).filter(
        has_label("component", component)
    )
    assert metrics.values, f"No values returned for 'kuadrant_component_ready' for component '{component}'"
    assert metrics.values[0] == 1, (
        f"Expected 'kuadrant_component_ready' for component '{component}' to have value 1, "
        f"but got values: {metrics.values}"
    )


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_metric_kuadrant_dependency_detected(operator_metrics, dependency):
    """Tests that kuadrant_dependency_detected metric has expected value for each dependency"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_dependency_detected")).filter(
        has_label("dependency", dependency)
    )
    assert metrics.values, f"No values returned for 'kuadrant_dependency_detected' for dependency '{dependency}'"
    if dependency in ("istio", "envoygateway"):
        assert metrics.values[0] in (
            1,
            0,
        ), (
            f"Expected 'kuadrant_dependency_detected' for '{dependency}' to have value 1 or 0, "
            f"but got: {metrics.values}"
        )
    else:
        assert (
            metrics.values[0] == 1
        ), f"Expected 'kuadrant_dependency_detected' for '{dependency}' to have value 1, but got: {metrics.values}"


@pytest.mark.parametrize("controller", CONTROLLERS)
def test_metric_kuadrant_controller_registered(operator_metrics, controller):
    """Tests that kuadrant_controller_registered metric has expected value for each controller"""
    metrics = operator_metrics.filter(has_label("__name__", "kuadrant_controller_registered")).filter(
        has_label("controller", controller)
    )
    assert metrics.values, f"No values returned for 'kuadrant_controller_registered' for controller '{controller}'"
    if controller in ("istio_integration", "envoygateway_integration"):
        assert metrics.values[0] in (
            1,
            0,
        ), (
            f"Expected 'kuadrant_controller_registered' for '{controller}' to have value 1 or 0, "
            f"but got: {metrics.values}"
        )
    else:
        assert metrics.values[0] == 1, (
            f"Expected 'kuadrant_controller_registered' for '{controller}' to have value 1, "
            f"but got: {metrics.values}"
        )
