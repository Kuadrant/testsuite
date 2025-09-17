"""Test Kuadrant operator resilience when its container is killed."""

import json
import pytest
import openshift_client as oc

pytestmark = [pytest.mark.disruptive, pytest.mark.kuadrant_only]


def test_operator_container_kill(cluster, kuadrant_operator_pod_chaos):
    """Test operator resilience when its container is killed."""
    # Check actual operator labels first
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"

    # Apply chaos
    kuadrant_operator_pod_chaos.commit()

    # Get logs after recovery
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        log_content = next(iter(pod.logs().values()))

        # Check each log line for errors
        errors = []
        for line in log_content.splitlines():
            try:
                log_entry = json.loads(line)
                if log_entry.get("level") == "error":
                    error_details = {
                        "msg": log_entry.get("msg", "Unknown error"),
                        "error": log_entry.get("error"),
                        "stacktrace": log_entry.get("stacktrace"),
                        "timestamp": log_entry.get("ts"),
                    }
                    # Remove None values for cleaner output
                    error_details = {k: v for k, v in error_details.items() if v is not None}
                    errors.append(error_details)
            except json.JSONDecodeError:
                continue  # Skip non-JSON lines

        assert not errors, f"Found errors in operator logs: {errors}"
