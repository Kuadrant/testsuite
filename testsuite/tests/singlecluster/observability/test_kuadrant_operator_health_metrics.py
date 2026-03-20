"""Tests for Kuadrant operator health metrics (existence, readiness, component and dependency status)."""

import pytest
from openshift_client import selector

from testsuite.prometheus import has_label

pytestmark = [pytest.mark.observability]


@pytest.fixture(scope="module")
def is_istio(cluster, skip_or_fail):
    """Skip if Istio is not installed on the cluster"""
    if not selector("Istio", all_namespaces=True, static_context=cluster.context).objects():
        skip_or_fail("Istio is not installed on the cluster")


def test_metric_kuadrant_exist(kuadrant_operator_metrics):
    """Tests that kuadrant_exists metric is present and has value 1"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_exists"))
    assert metrics, "'kuadrant_exists' metric wasn't found"
    assert metrics.values[0] == 1, f"Expected 'kuadrant_exists' to have value 1, but got values: {metrics.values}"


def test_metric_kuadrant_ready(kuadrant_operator_metrics, kuadrant):
    """Tests that kuadrant_ready metric is present and has value 1"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_ready")).filter(
        has_label("name", kuadrant.name())
    )
    assert metrics, "'kuadrant_ready' metric wasn't found"
    assert metrics.values[0] == 1, f"Expected 'kuadrant_ready' to have value 1, but got values: {metrics.values}"


@pytest.mark.parametrize("component", ["authorino", "limitador"])
def test_metric_kuadrant_component_ready(kuadrant_operator_metrics, component):
    """Tests that kuadrant_component_ready metric is present and has value 1 for each component"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_component_ready")).filter(
        has_label("component", component)
    )
    assert metrics, f"'kuadrant_component_ready' metric wasn't found for component '{component}'"
    assert metrics.values[0] == 1, (
        f"Expected 'kuadrant_component_ready' for component '{component}' to have value 1, "
        f"but got values: {metrics.values}"
    )


@pytest.mark.parametrize(
    "dependency",
    [
        "authorino-operator",
        "limitador-operator",
        "cert-manager",
        "dns-operator",
    ],
)
def test_metric_kuadrant_dependency_detected(kuadrant_operator_metrics, dependency):
    """Tests that kuadrant_dependency_detected metric has expected value for each dependency"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_dependency_detected")).filter(
        has_label("dependency", dependency)
    )
    assert metrics, f"'kuadrant_dependency_detected' metric wasn't found for dependency '{dependency}'"
    assert (
        metrics.values[0] == 1
    ), f"Expected 'kuadrant_dependency_detected' for '{dependency}' to be 1, but got: {metrics.values}"


@pytest.mark.parametrize(
    "dependency, expected",
    [
        ("istio", 1),
        ("envoygateway", 0),
    ],
)
def test_metric_kuadrant_gateway_provider_detected(
    kuadrant_operator_metrics, dependency, expected, is_istio
):  # pylint: disable=unused-argument
    """Tests that gateway provider dependencies are correctly detected when Istio is installed"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_dependency_detected")).filter(
        has_label("dependency", dependency)
    )
    assert metrics, f"'kuadrant_dependency_detected' metric wasn't found for dependency '{dependency}'"
    assert (
        metrics.values[0] == expected
    ), f"Expected 'kuadrant_dependency_detected' for '{dependency}' to be {expected}, but got: {metrics.values}"


@pytest.mark.parametrize(
    "controller",
    [
        "auth_policies",
        "rate_limit_policies",
        "dns_policies",
        "tls_policies",
    ],
)
def test_metric_kuadrant_controller_registered(kuadrant_operator_metrics, controller):
    """Tests that kuadrant_controller_registered metric has expected value for each controller"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_controller_registered")).filter(
        has_label("controller", controller)
    )
    assert metrics, f"'kuadrant_controller_registered' metric wasn't found for controller '{controller}'"
    assert (
        metrics.values[0] == 1
    ), f"Expected 'kuadrant_controller_registered' for '{controller}' to be 1, but got: {metrics.values}"


@pytest.mark.parametrize(
    "controller, expected",
    [
        ("istio_integration", 1),
        ("envoygateway_integration", 0),
    ],
)
def test_metric_kuadrant_gateway_controller_registered(
    kuadrant_operator_metrics, controller, expected, is_istio
):  # pylint: disable=unused-argument
    """Tests that gateway provider controllers are correctly registered when Istio is installed"""
    metrics = kuadrant_operator_metrics.filter(has_label("__name__", "kuadrant_controller_registered")).filter(
        has_label("controller", controller)
    )
    assert metrics, f"'kuadrant_controller_registered' metric wasn't found for controller '{controller}'"
    assert (
        metrics.values[0] == expected
    ), f"Expected 'kuadrant_controller_registered' for '{controller}' to be {expected}, but got: {metrics.values}"
