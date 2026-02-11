"""Test Kuadrant operator resilience when its container is killed."""

import json
import pytest
import openshift_client as oc

pytestmark = [pytest.mark.disruptive, pytest.mark.kuadrant_only]


def test_operator_container_kill_basic(cluster, operator_chaos_factory):
    """Test basic operator container kill and recovery."""
    kuadrant_system = cluster.change_project("kuadrant-system")
    
    # Verify operator is running
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"

    # Apply chaos - kill container
    chaos = operator_chaos_factory("container-kill-basic", "container-kill")
    chaos.commit()

    # Verify recovery and check logs
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        log_content = next(iter(pod.logs().values()))

        # Check for error-level logs
        errors = []
        for line in log_content.splitlines():
            try:
                log_entry = json.loads(line)
                if log_entry.get("level") == "error":
                    error_details = {
                        "msg": log_entry.get("msg", "Unknown error"),
                        "error": log_entry.get("error"),
                        "timestamp": log_entry.get("ts"),
                    }
                    error_details = {k: v for k, v in error_details.items() if v is not None}
                    errors.append(error_details)
            except json.JSONDecodeError:
                continue

        assert not errors, f"Found errors in operator logs: {errors}"
