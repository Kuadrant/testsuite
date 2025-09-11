"""Test Kuadrant operator resilience when its container is killed."""

import pytest

pytestmark = [pytest.mark.chaos, pytest.mark.disruptive, pytest.mark.kuadrant_only]


def test_operator_pod_kill(operator_pod_chaos, authorization):
    """Test operator resilience when its container is killed."""
    # Wait for operator to recover and reconcile
    assert authorization.wait_until_ready()

    # Verify operator is functioning by checking policy status
    assert authorization.wait_until_enforced()