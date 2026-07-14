"""Tests for PipelinePolicy gRPC error handling: unavailable services, wrong names, and fail actions."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own PipelinePolicy."""


def test_grpc_upstream_unavailable(request, cluster, blame, route):
    """PipelinePolicy reports error when action method URL points to a non-existent service."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-url"), route)
    policy.add_action_method(
        name="bad-method",
        url="grpc://does-not-exist.default.svc.cluster.local:8080",
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    policy.on_http_request.add_grpc_method(method="bad-method")

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown", message="produced zero addresses"),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"


def test_grpc_wrong_service_name(request, cluster, blame, route, threat_service_url):
    """PipelinePolicy reports error when action method references a non-existent gRPC service name."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-svc"), route)
    policy.add_action_method(
        name="bad-service",
        url=threat_service_url,
        service="nonexistent.v1.FakeService",
        method="DoSomething",
        message_template="nonexistent.v1.FakeRequest{uri: request.path}",
    )
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    policy.on_http_request.add_grpc_method(method="bad-service")

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown", message="failed to fetch service"),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"


def test_grpc_wrong_method_name(request, cluster, blame, route, threat_service_url):
    """PipelinePolicy reports error when action method references a non-existent gRPC method."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-meth"), route)
    policy.add_action_method(
        name="wrong-method",
        url=threat_service_url,
        service="threat.v1.ThreatAssessmentService",
        method="NonExistentMethod",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    policy.on_http_request.add_grpc_method(method="wrong-method")

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown", message='method "NonExistentMethod" not found in service'),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"
