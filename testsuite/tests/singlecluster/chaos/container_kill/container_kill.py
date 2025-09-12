"""Test Kuadrant operator resilience when its container is killed."""

import pytest
import openshift_client as oc

pytestmark = [pytest.mark.disruptive, pytest.mark.kuadrant_only]


def test_kuadrant_operator_container_kill(cluster, operator_pod_chaos):
    """Test operator resilience when its container is killed."""
    # Check actual operator labels first
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.status() == "Running"

    # Apply chaos
    operator_pod_chaos.commit()

    # Get logs after recovery
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        logs = pod.logs()

        # Get the log content (first and only value in the dict)
        log_content = next(iter(logs.values()))

        expected_error = "unable to start extension manager"
        socket_error = "address already in use"

        assert (
            expected_error in log_content and socket_error in log_content
        ), "Expected extension manager error about socket already in use not found in logs"
