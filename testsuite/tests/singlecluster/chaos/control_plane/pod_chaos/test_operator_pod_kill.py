"""Test Kuadrant operator resilience with pod-kill chaos."""

import pytest
import openshift_client as oc

pytestmark = [pytest.mark.disruptive, pytest.mark.kuadrant_only]


def test_operator_pod_kill_basic(cluster, operator_chaos_factory):
    """Test basic operator pod kill and recovery."""
    kuadrant_system = cluster.change_project("kuadrant-system")
    
    # Verify operator is running
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"
        original_pod_name = pod.model.metadata.name

    # Apply chaos - kill pod
    chaos = operator_chaos_factory("pod-kill-basic", "pod-kill")
    chaos.commit()

    # Verify new pod is created and running
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"
        # Should be a different pod
        assert pod.model.metadata.name != original_pod_name


def test_operator_pod_kill_with_grace_period(cluster, operator_chaos_factory):
    """Test operator pod kill with custom grace period."""
    # Create chaos with 30s grace period
    chaos = operator_chaos_factory("graceful-kill", "pod-kill", grace_period=30)
    chaos.commit()
    
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"


def test_operator_pod_kill_immediate(cluster, operator_chaos_factory):
    """Test operator pod kill with immediate termination."""
    # Create chaos with 0s grace period (immediate kill)
    chaos = operator_chaos_factory("immediate-kill", "pod-kill", grace_period=0)
    chaos.commit()
    
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"


def test_operator_pod_failure_recovery(cluster, operator_chaos_factory):
    """Test operator recovery from pod failure."""
    kuadrant_system = cluster.change_project("kuadrant-system")
    
    # Apply chaos - make pod fail
    chaos = operator_chaos_factory("pod-failure-recovery", "pod-failure")
    chaos.commit()
    
    # Verify operator eventually recovers
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"


def test_operator_pod_failure_custom_duration(cluster, operator_chaos_factory):
    """Test operator pod failure with custom duration."""
    # Create chaos with longer failure duration
    chaos = operator_chaos_factory("long-failure", "pod-failure", duration="60s")
    chaos.commit()
    
    kuadrant_system = cluster.change_project("kuadrant-system")
    with kuadrant_system.context:
        pod = oc.selector("pod", labels={"app": "kuadrant"}).object()
        assert pod.model.status.phase == "Running"
