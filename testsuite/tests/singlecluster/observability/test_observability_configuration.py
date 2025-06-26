"""
Tests observability configuration after Kuadrant CR changes
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]


def test_no_monitors_and_labels_exist_by_default(
    gateway, get_all_monitors, reset_observability
):  # pylint: disable=unused-argument
    """Verify no ServiceMonitor / PodMonitor resources or observability labels exist by default"""
    reset_observability()

    servicemonitors, podmonitors = get_all_monitors()

    assert not servicemonitors, "ServiceMonitor resources exist"
    assert not podmonitors, "PodMonitor resources exist"

    for monitor in servicemonitors + podmonitors:
        labels = monitor.model.metadata.labels or {}
        assert (
            "kuadrant.io/observability" not in labels
        ), f"Unexpected observability label on {monitor.kind()} {monitor.name()} in {monitor.namespace()}"


def test_monitors_and_labels_created_in_expected_namespaces_when_enabled(
    gateway, configure_observability, wait_for_monitors, get_all_monitors, testconfig, reset_observability
):  # pylint: disable=unused-argument
    """Verify monitors are created in expected namespaces and labeled when observability is enabled"""
    configure_observability(True)
    wait_for_monitors(present=True)  # wait for monitors to be created

    servicemonitors, podmonitors = get_all_monitors()
    all_monitors = servicemonitors + podmonitors
    assert all_monitors, "No ServiceMonitor or PodMonitor resources found"

    expected_namespaces = {
        testconfig["service_protection"]["system_project"],
        testconfig["service_protection"]["project"],
    }
    actual_namespaces = {m.namespace() for m in all_monitors}

    missing = expected_namespaces - actual_namespaces
    assert not missing, f"Missing monitors in expected namespaces: {missing}"

    for monitor in all_monitors:
        labels = monitor.model.metadata.labels or {}
        assert (
            labels.get("kuadrant.io/observability") == "true"
        ), f"Missing or incorrect label on {monitor.kind()} {monitor.name()} in {monitor.namespace()}"


def test_no_monitors_and_labels_exist_when_disabled(
    gateway, configure_observability, wait_for_monitors, get_all_monitors, reset_observability
):  # pylint: disable=unused-argument
    """Verify that all monitors and observability labels are removed when observability is disabled"""
    configure_observability(True)
    wait_for_monitors(present=True)

    configure_observability(False)
    wait_for_monitors(present=False)

    servicemonitors, podmonitors = get_all_monitors()

    assert not servicemonitors, "ServiceMonitor resources exist"
    assert not podmonitors, "PodMonitor resources exist"

    for monitor in servicemonitors + podmonitors:
        labels = monitor.model.metadata.labels or {}
        assert (
            "kuadrant.io/observability" not in labels
        ), f"Unexpected observability label on {monitor.kind()} {monitor.name()} in {monitor.namespace()}"
